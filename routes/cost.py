from datetime import datetime, timedelta, date

from flask import Blueprint, render_template, request, flash, session, redirect, url_for
from flask_login import login_required

cost_bp = Blueprint("cost", __name__)

# Chosen limits reflect realistic Nepali smallholder farming values:
MAX_COST_RS = 500_000    # Rs 5 lakh per input — covers large-scale fields
MAX_YIELD_KG = 100_000   # 100 tonnes — generous upper bound
MAX_PRICE_RS = 500       # Rs 500/kg — tomatoes rarely exceed this
MAX_DAYS_PAST = 365      # planting date cannot be more than 1 year ago


@cost_bp.route("/cost", methods=["GET", "POST"])
@login_required
def cost():
    if request.method == "POST":
        # Check which form was submitted
        if "calculate_investment" in request.form:
            # Investment calculation only
            try:
                seeds = float(request.form["seeds"])
                fertilizer = float(request.form["fertilizer"])
                water = float(request.form["water"])
                expected_yield = float(request.form["yield"])
            except (ValueError, KeyError):
                flash("Please enter valid numbers for investment calculation.", "error")
                return render_template("cost.html")

            if any(v < 0 for v in (seeds, fertilizer, water, expected_yield)):
                flash("All investment values must be zero or positive.", "error")
                return render_template("cost.html")

            if water <= 0:
                flash("Water cost must be greater than zero.", "error")
                return render_template("cost.html")

            if expected_yield <= 0:
                flash("Expected yield must be greater than zero.", "error")
                return render_template("cost.html")

            if seeds > MAX_COST_RS or fertilizer > MAX_COST_RS or water > MAX_COST_RS:
                flash(f"Individual cost values cannot exceed Rs {MAX_COST_RS:,}.", "error")
                return render_template("cost.html")

            if expected_yield > MAX_YIELD_KG:
                flash(f"Expected yield cannot exceed {MAX_YIELD_KG:,} kg.", "error")
                return render_template("cost.html")

            total_cost = seeds + fertilizer + water
            
            # Store investment data in session for later use
            session['investment_data'] = {
                'seeds': seeds,
                'fertilizer': fertilizer,
                'water': water,
                'expected_yield': expected_yield,
                'total_cost': total_cost
            }
            
            flash(f"Total investment calculated: Rs {total_cost:,.2f}. You can now set market price to plan your profit.", "success")
            return render_template(
                "cost.html",
                seeds=seeds,
                fertilizer=fertilizer,
                water=water,
                expected_yield=expected_yield,
                total_cost=round(total_cost, 2),
                show_price_form=True  # Show market price form
            )
            
        elif "calculate_profit" in request.form:
            # Profit calculation with market price
            try:
                market_price = float(request.form["market_price"])
            except (ValueError, KeyError):
                flash("Please enter a valid market price.", "error")
                return render_template("cost.html")

            if market_price > MAX_PRICE_RS:
                flash(f"Market price cannot exceed Rs {MAX_PRICE_RS:,} per kg.", "error")
                return render_template("cost.html")

            if market_price < 0:
                flash("Market price must be positive.", "error")
                return render_template("cost.html")

            # Get investment data from session
            investment_data = session.get('investment_data')
            if not investment_data:
                flash("Please calculate your investment first.", "error")
                return render_template("cost.html")

            expected_yield = investment_data['expected_yield']
            total_cost = investment_data['total_cost']
            
            revenue = expected_yield * market_price
            net_profit = revenue - total_cost
            is_loss = net_profit < 0
            
            # Calculate break-even price
            break_even_price = total_cost / expected_yield if expected_yield > 0 else 0
            
            # Calculate profit margin
            profit_margin = (net_profit / total_cost) * 100 if total_cost > 0 else 0
            
            # Recommended price for desired profit margin
            desired_profit_margin = 30  # 30% profit margin recommendation
            recommended_price = (total_cost * (1 + desired_profit_margin / 100)) / expected_yield if expected_yield > 0 else 0

            return render_template(
                "cost.html",
                seeds=investment_data['seeds'],
                fertilizer=investment_data['fertilizer'],
                water=investment_data['water'],
                expected_yield=expected_yield,
                total_cost=round(total_cost, 2),
                market_price=round(market_price, 2),
                revenue=round(revenue, 2),
                net_profit=round(net_profit, 2),
                net_amount=round(abs(net_profit), 2),
                is_loss=is_loss,
                break_even_price=round(break_even_price, 2),
                profit_margin=round(profit_margin, 2),
                recommended_price=round(recommended_price, 2),
                show_results=True
            )
            
        elif "reset" in request.form:
            # Clear session data and reset form
            session.pop('investment_data', None)
            flash("All data cleared. Start a new calculation.", "info")
            return redirect(url_for('cost.cost'))
    
    # GET request - check if there's existing investment data
    investment_data = session.get('investment_data')
    if investment_data:
        return render_template(
            "cost.html",
            seeds=investment_data['seeds'],
            fertilizer=investment_data['fertilizer'],
            water=investment_data['water'],
            expected_yield=investment_data['expected_yield'],
            total_cost=round(investment_data['total_cost'], 2),
            show_price_form=True
        )
    
    return render_template("cost.html")


@cost_bp.route("/time", methods=["GET", "POST"])
@login_required
def time_calc():
    if request.method == "POST":
        try:
            planting_date = datetime.strptime(
                request.form["planting_date"], "%Y-%m-%d"
            ).date()
        except (ValueError, KeyError):
            flash("Please enter a valid planting date for time calculation.", "error")
            return render_template("time.html")

        today = date.today()
        days_ago = (today - planting_date).days
        if days_ago < 0:
            flash("Planting date cannot be in the future.", "error")
            return render_template("time.html")
        if days_ago > MAX_DAYS_PAST:
            flash("Planting date cannot be more than 1 year ago.", "error")
            return render_template("time.html")

        harvest_min = planting_date + timedelta(days=70)
        harvest_max = planting_date + timedelta(days=90)
        days_until_min = (harvest_min - today).days
        days_until_max = (harvest_max - today).days

        weeks_since_planting = days_ago // 7
        remaining_days = days_ago % 7
        if weeks_since_planting > 0:
            crop_age_text = f"{weeks_since_planting} week(s) and {remaining_days} day(s)"
        else:
            crop_age_text = f"{days_ago} day(s)"

        if days_until_max < 0:
            harvest_status = "Harvest period has passed."
        elif days_until_min <= 0:
            harvest_status = "Harvest is currently ongoing!"
        else:
            harvest_status = f"Harvest expected in {days_until_min}–{days_until_max} days."

        return render_template(
            "time.html",
            days_since_planting=days_ago,
            crop_age_text=crop_age_text,
            planting_date_display=planting_date.strftime("%d %b %Y"),
            today_display=today.strftime("%d %b %Y"),
            harvest_window_display=(
                f"{harvest_min.strftime('%d %b %Y')} to {harvest_max.strftime('%d %b %Y')}"
            ),
            harvest_status=harvest_status,
        )

    return render_template("time.html")
