def calculate_targets(profile: dict, goal: str) -> dict:
    age = int(profile["age"])
    sex = profile["sex"]              # male/female
    h = float(profile["height_cm"])
    w = float(profile["weight_kg"])
    act = float(profile["activity_factor"])

    # Mifflin–St Jeor
    if sex == "male":
        bmr = 10*w + 6.25*h - 5*age + 5
    else:
        bmr = 10*w + 6.25*h - 5*age - 161

    tdee = bmr * act

    if goal == "lose":
        calories = tdee * 0.82
        protein = 1.7 * w
        fat = 0.8 * w
    elif goal == "gain":
        calories = tdee * 1.12
        protein = 1.8 * w
        fat = 0.9 * w
    elif goal == "health":
        calories = tdee * 0.95
        protein = 1.6 * w
        fat = 0.9 * w
    else:  # maintain
        calories = tdee
        protein = 1.6 * w
        fat = 0.9 * w

    calories = max(1200, calories)
    carbs = (calories - protein*4 - fat*9) / 4
    carbs = max(0, carbs)

    return {
        "calories": float(calories),
        "protein_g": float(protein),
        "fat_g": float(fat),
        "carbs_g": float(carbs)
    }