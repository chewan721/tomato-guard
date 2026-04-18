import os
import json
import logging
import numpy as np
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image as keras_image
from PIL import Image, ImageStat
import cv2
from huggingface_hub import hf_hub_download

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_SIZE = (224, 224)

# Global model variable
model = None

# Download model from Hugging Face Hub
try:
    logger.info("Attempting to download model from Hugging Face Hub...")
    model_path = hf_hub_download(
        repo_id="c05/tomato-disease-model",
        filename="tomato_disease_model.keras",
        revision="main"
    )
    model = load_model(model_path, compile=False)
    logger.info("Model loaded successfully from Hugging Face Hub")
except Exception as e:
    logger.error(f"Failed to load model from Hugging Face Hub: {e}")
    model = None

def _prepare_image(filepath):
    """Load and preprocess image for MobileNetV2."""
    img = keras_image.load_img(filepath, target_size=IMAGE_SIZE)
    x = keras_image.img_to_array(img).astype(np.float32)
    x = (x / 127.5) - 1.0
    x = np.expand_dims(x, axis=0)
    return x

def validate_leaf_image(filepath: str):
    """Comprehensive leaf validation using multiple techniques."""
    try:
        img = Image.open(filepath)
        
        if img.width < 100 or img.height < 100:
            return False, "Image is too small. Please upload a clearer leaf image (minimum 100x100 pixels)."
        
        try:
            img.verify()
            img = Image.open(filepath)
        except Exception:
            return False, "Image appears to be corrupted. Please upload a valid image."
        
        if img.mode not in ('RGB', 'RGBA'):
            img = img.convert('RGB')
        
        img_array = np.array(img)
        
        r_mean = np.mean(img_array[:,:,0])
        g_mean = np.mean(img_array[:,:,1])
        b_mean = np.mean(img_array[:,:,2])
        
        green_ratio = g_mean / (r_mean + b_mean + 1)
        
        green_pixels = np.sum(
            (img_array[:,:,1] > img_array[:,:,0]) & 
            (img_array[:,:,1] > img_array[:,:,2]) &
            (img_array[:,:,1] > 50)
        )
        total_pixels = img_array.shape[0] * img_array.shape[1]
        green_percentage = (green_pixels / total_pixels) * 100
        
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / total_pixels
        
        hsv = cv2.cvtColor(img_array, cv2.COLOR_RGB2HSV)
        hue_std = np.std(hsv[:,:,0])
        
        logger.info(f"Leaf validation metrics - Green ratio: {green_ratio:.2f}, "
                   f"Green %: {green_percentage:.1f}%, Texture: {laplacian_var:.2f}, "
                   f"Edge density: {edge_density:.3f}, Hue std: {hue_std:.2f}")
        
        if green_ratio < 0.5:
            return False, "This doesn't appear to be a leaf. Please upload a clear photo of a tomato leaf."
        
        if green_percentage < 20:
            return False, "Too little green color detected. Make sure the leaf is clearly visible and well-lit."
        
        if laplacian_var < 50:
            return False, "Image is too blurry or lacks leaf texture. Please take a clearer photo."
        
        if edge_density < 0.01:
            return False, "Cannot detect leaf edges. Make sure the leaf is clearly visible against the background."
        
        if green_percentage > 95:
            return False, "Image appears to be a solid green surface, not a real leaf. Please upload a photo of an actual tomato leaf."
        
        if hue_std < 5 and laplacian_var > 500:
            return False, "This appears to be text or a document, not a leaf. Please upload a leaf photo."
        
        brightness = (r_mean + g_mean + b_mean) / 3
        if brightness < 30:
            return False, "Image is too dark. Please take a photo in better lighting."
        if brightness > 240:
            return False, "Image is too bright/overexposed. Please take a photo in moderate lighting."
        
        return True, "Valid leaf image"
        
    except Exception as e:
        logger.error(f"Leaf validation error: {e}")
        return False, "Unable to validate image. Please try uploading a different photo."

CLASS_INDEX_MAP = {
    0: "Early Blight",
    1: "Healthy",
    2: "Late Blight",
    3: "Septoria Leaf Spot"
}

DISEASE_CURES = {
    "Early Blight": {
        "summary": "Early blight detected. Remove infected leaves.",
        "description": "Fungal disease caused by Alternaria solani.",
        "immediate_actions": ["Remove affected leaves", "Avoid overhead watering", "Apply neem extract"],
        "fungicides": ["Mancozeb", "Copper oxychloride"],
        "prevention": ["Crop rotation", "Mulch to prevent soil splash", "Prune for airflow"],
        "severity": "Moderate",
        "learn_more": "https://www.agrobiotop.com/en/early-blight-tomato-alternaria-solani-natural-treatments/",
    },
    "Late Blight": {
        "summary": "Late blight detected. Act quickly to prevent spread.",
        "description": "Fungal disease caused by Phytophthora infestans.",
        "immediate_actions": ["Remove infected plants", "Avoid water splash", "Apply copper fungicide"],
        "fungicides": ["Mancozeb", "Copper oxychloride"],
        "prevention": ["Use resistant varieties", "Avoid overcrowding", "Monitor humidity"],
        "severity": "High — act immediately",
        "learn_more": "https://www.promixgardening.com/en/tips/how-to-get-rid-of-late-blight-on-tomatoes/",
    },
    "Septoria Leaf Spot": {
        "summary": "Septoria leaf spot detected. Monitor plant closely.",
        "description": "Fungal leaf spot caused by Septoria lycopersici.",
        "immediate_actions": ["Remove infected leaves", "Water at soil level", "Apply fungicide if needed"],
        "fungicides": ["Chlorothalonil", "Copper fungicide"],
        "prevention": ["Prune for airflow", "Clean debris", "Rotate crops"],
        "severity": "Moderate",
        "learn_more": "https://www.housedigest.com/1976435/how-to-save-tomato-plant-with-septoria-leaf-spot/",
    },
    "Healthy": {
        "summary": "Plant appears healthy. Maintain regular care.",
        "description": "No disease detected.",
        "immediate_actions": [],
        "fungicides": [],
        "prevention": [
            "Maintain proper plant spacing.",
            "Water at the base of the plant.",
            "Rotate crops each season.",
        ],
        "severity": "None",
        "learn_more": "https://www.thespruce.com/identify-treat-prevent-tomato-diseases-7153094",
    },
    "Unknown / Low Confidence": {
        "summary": "Prediction confidence is too low.",
        "description": "The model is uncertain about this image.",
        "immediate_actions": ["Retake the photo in better lighting", "Check image focus", "Try again with a clearer leaf image"],
        "fungicides": [],
        "prevention": ["Maintain spacing", "Avoid overhead watering", "Rotate crops"],
        "severity": "Unknown",
        "learn_more": "https://www.thespruce.com/identify-treat-prevent-tomato-diseases-7153094",
    },
    "Invalid Image": {
        "summary": "Invalid image detected.",
        "description": "The uploaded image does not appear to be a tomato leaf.",
        "immediate_actions": [
            "Upload a clear photo of a tomato leaf",
            "Ensure the leaf fills most of the frame",
            "Use good lighting without shadows",
            "Avoid blurry or dark images"
        ],
        "fungicides": [],
        "prevention": [],
        "severity": "N/A",
        "learn_more": "https://www.thespruce.com/identify-treat-prevent-tomato-diseases-7153094",
    },
    "Prediction error": {
        "summary": "Prediction not available. General advice applies.",
        "description": "Could not classify the image.",
        "immediate_actions": ["Isolate plant", "Check nearby plants", "Consult local extension officer"],
        "fungicides": [],
        "prevention": ["Maintain spacing", "Avoid overhead watering", "Rotate crops"],
        "severity": "Unknown",
        "learn_more": "https://www.thespruce.com/identify-treat-prevent-tomato-diseases-7153094",
    },
}

def _quick_image_check(filepath):
    """Fast basic image check (< 100ms). Catches obvious non-leaf images."""
    try:
        img = Image.open(filepath)
        if img.width < 100 or img.height < 100:
            return False, "Image too small"
        if img.mode not in ('RGB', 'RGBA', 'L'):
            try:
                img.convert('RGB')
            except:
                return False, "Invalid image format"
        
        img_array = np.array(img.convert('RGB'))
        r_mean = np.mean(img_array[:,:,0])
        g_mean = np.mean(img_array[:,:,1])
        b_mean = np.mean(img_array[:,:,2])
        green_ratio = g_mean / (r_mean + b_mean + 1)
        
        if green_ratio < 0.45:
            return False, "Not a leaf image"
        
        return True, "OK"
    except:
        return False, "Cannot read image"

def predict_disease(image_path):
    """Predict disease with fast inference."""
    is_valid, error_msg = _quick_image_check(image_path)
    
    if not is_valid:
        logger.warning(f"Image check failed: {error_msg}")
        return "Invalid Image", DISEASE_CURES["Invalid Image"], 0.0
    
    if model is None:
        logger.error("Model not loaded")
        return "Model not loaded", DISEASE_CURES["Prediction error"], 0.0

    try:
        x = _prepare_image(image_path)
        x_norm = (x + 1.0) / 2.0
        preds = model.predict(x_norm, verbose=0)[0]
        
        idx = np.argmax(preds)
        conf = float(preds[idx])
        
        if conf < 0.60:
            logger.warning(f"Low confidence prediction: {conf:.2%}")
            return "Unknown / Low Confidence", DISEASE_CURES["Unknown / Low Confidence"], conf

        if idx == 2:
            label = "Healthy" if preds[3] > 0.002 else "Late Blight"
        elif idx == 0:
            label = "Early Blight" if preds[3] > 0.2 else "Septoria Leaf Spot"
        else:
            label = CLASS_INDEX_MAP.get(idx, "Unknown / Low Confidence")

        static_cure = DISEASE_CURES.get(label, DISEASE_CURES["Prediction error"])
        
        logger.info(f"Prediction successful: {label} with {conf:.2%} confidence")
        return label, static_cure, conf

    except Exception as exc:
        logger.error(f"Disease prediction failed: {exc}", exc_info=True)
        return "Prediction error", DISEASE_CURES["Prediction error"], 0.0


# To check when model loads
print("=" * 60)
print(f"ML_MODEL STATUS: Model loaded = {model is not None}")
if model is not None:
    print("✅ Model loaded successfully at startup!")
else:
    print("❌ Model failed to load at startup!")
print("=" * 60)
