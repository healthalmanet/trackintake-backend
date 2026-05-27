# TrackIntake Integration API Guide

> [!IMPORTANT]
> **Base URL Configuration:** All endpoints documented here must be requested against the **TrackIntake Backend Base URL** (e.g., `http://127.0.0.1:8000` or your deployed TrackIntake server domain), NOT your own project's backend URL. Make sure your API client is configured with the correct Base URL.

This document outlines the public/integration API endpoints designed for third-party project integration. These endpoints allow direct registration (without OTP verification), plan listing, real Razorpay checkout, subscription verification, profile & health profile management, and AI diet plan generation.

All data created or modified through these APIs is stored in the shared database, meaning users can seamlessly log in on the main TrackIntake website and see all their synced data, profiles, and diet plans.

---

## 🔑 Authentication & Token Flow

All endpoints (except **Registration** and **Plan Listing**) require JWT Bearer Authentication. Your application can obtain the necessary JWT access token in two ways:

### A. Upon Successful Registration
The register endpoint (`POST /api/integration/register/`) returns the `access` and `refresh` tokens directly in the HTTP response body on success. You can store and use the access token immediately.

### B. Logging in an Existing User
If a user is already registered, perform a standard Login request to obtain new JWT tokens:
* **Endpoint:** `POST /api/login/`
* **Request Body:**
  ```json
  {
    "email": "user@example.com",
    "password": "securepassword123"
  }
  ```
* **Success Response:** Returns standard simple-jwt tokens (e.g., access and refresh).

---

## 🔒 Request Headers
Once you have the access token, include it in the headers of all subsequent API calls:

```http
Authorization: Bearer <YOUR_ACCESS_TOKEN>
```

---

## 🚀 API Endpoints

### 1. Register User (Direct Signup)
* **Endpoint:** `POST /api/integration/register/`
* **Authentication:** None (Public)
* **Description:** Creates a user account directly without requiring email OTP verification. For patients (`role: "user"`), it automatically initializes their `UserProfile` and assigns the **Free Plan** (if one exists).

#### Request Body:
```json
{
  "email": "user@example.com",
  "full_name": "John Doe",
  "password": "securepassword123",
  "role": "user", // "user" (default) or "nutritionist"
  
  // Optional profile fields (only processed if role is "user")
  "gender": "male", // "male", "female", or "other"
  "date_of_birth": "1995-08-15", // YYYY-MM-DD
  "country": "India",
  "city": "Mumbai",
  "mobile_number": "9876543210",
  "height_cm": 175.5,
  "weight_kg": 72.0,
  "activity_level": "Moderately Active", // "Sedentary", "Lightly Active", "Moderately Active", "Very Active", "Extra Active"
  "goal": "Lose Weight", // "Lose Weight", "Maintain Weight", "Gain Weight"
  "diet_type": "Vegetarian", // "Vegetarian", "Non Vegetarian", "Vegan", "Eggetarian", "Keto", "Other"
  "allergies": "Peanuts, Gluten",
  
  // Health profile flags (Boolean)
  "is_diabetic": false,
  "is_hypertensive": false,
  "has_heart_condition": false,
  "has_thyroid_disorder": false,
  "has_arthritis": false,
  "has_gastric_issues": false,
  "other_chronic_condition": "None",
  "family_history": "Grandfather had type-2 diabetes",
  
  // Pregnancy & Postpartum fields (for female users)
  "is_pregnant": false,
  "due_date": null,
  "is_breastfeeding": false
}
```

#### Success Response (`201 Created`):
```json
{
  "message": "User registered successfully.",
  "tokens": {
    "refresh": "<JWT_REFRESH_TOKEN>",
    "access": "<JWT_ACCESS_TOKEN>"
  },
  "user": {
    "id": 42,
    "email": "user@example.com",
    "full_name": "John Doe",
    "role": "user"
  }
}
```

---

### 2. List Subscription Plans
* **Endpoint:** `GET /api/integration/plans/`
* **Authentication:** None (Public)
* **Description:** Retrieves all active subscription plans for patients.

#### Success Response (`200 OK`):
```json
[
  {
    "id": 1,
    "name": "Free Plan",
    "price": 0,
    "duration_days": 30,
    "plan_type": "patient",
    "features": {
      "weight_tracker_allowed": true,
      "nutrition_search_allowed": true,
      "custom_reminder_allowed": false,
      "chat_allowed": false,
      "appointment_allowed": false,
      "ai_diet_allowed": true,
      "BMI_Calculator_allowed": true,
      "Fat_Calculator_allowed": false,
      "meal_log_allowed": true,
      "water_intake_allowed": true
    },
    "consultations": {
      "expert_consults": 0,
      "inhouse_consults": 0,
      "inhouse_consultation_fee": 200,
      "expert_consultation_fee": 500
    }
  }
]
```

---

### 3. Create Razorpay Payment Order
* **Endpoint:** `POST /api/integration/create-order/`
* **Authentication:** JWT Bearer (Required)
* **Description:** Initiates a plan purchase. It connects directly with Razorpay using server credentials to generate a real Razorpay Order and saves a pending Payment entry in the database.

#### Request Body:
```json
{
  "plan_id": 2
}
```

#### Success Response (`201 Created`):
```json
{
  "order_id": "order_OkG391klD91sH",
  "amount": 29900, // In paise (e.g. 299.00 INR)
  "currency": "INR",
  "key": "rzp_test_YourKeyHere",
  "plan": {
    "id": 2,
    "name": "Standard Plan",
    "price": 299
  }
}
```

---

### 4. Verify Razorpay Payment Signature
* **Endpoint:** `POST /api/integration/verify-payment/`
* **Authentication:** JWT Bearer (Required)
* **Description:** Verifies the cryptographic signature returned by the Razorpay checkout modal. If valid, marks the payment as successful and activates the corresponding subscription plan.

#### Request Body:
```json
{
  "razorpay_order_id": "order_OkG391klD91sH",
  "razorpay_payment_id": "pay_OkG4n29D29aK",
  "razorpay_signature": "9d81d2938ac...f82810a91f38"
}
```

#### Success Response (`200 OK`):
```json
{
  "message": "Payment verified and plan activated successfully.",
  "subscription": {
    "id": 15,
    "plan_name": "Standard Plan",
    "plan_type": "patient",
    "start_date": "2026-05-24",
    "end_date": "2026-06-23",
    "is_active": true
  }
}
```

---

### 5. Check Active Subscription Plan
* **Endpoint:** `GET /api/integration/check-subscription/`
* **Authentication:** JWT Bearer (Required)
* **Description:** Checks if the patient user has an active subscription. Highly useful for frontend gates/middleware blocking access to diet plans or premium features until a plan is purchased.

#### Success Response (`200 OK` - User has a plan):
```json
{
  "has_active_plan": true,
  "plan": {
    "id": 2,
    "name": "Standard Plan",
    "price": 299,
    "expires_at": "2026-06-23"
  }
}
```

#### Success Response (`200 OK` - User does NOT have a plan):
```json
{
  "has_active_plan": false,
  "plan": null
}
```

---

### 6. Get User Profile
* **Endpoint:** `GET /api/integration/profile/`
* **Authentication:** JWT Bearer (Required)
* **Description:** Fetches the logged-in patient's physical and health metrics.

#### Success Response (`200 OK`):
```json
{
  "date_of_birth": "1995-08-15",
  "age": 30,
  "country": "India",
  "city": "Mumbai",
  "mobile_number": "9876543210",
  "gender": "male",
  "height_cm": 175.5,
  "weight_kg": 72.0,
  "bmi": 23.37,
  "occupation": "Software Engineer",
  "activity_level": "Moderately Active",
  "goal": "Lose Weight",
  "diet_type": "Vegetarian",
  "allergies": "Peanuts, Gluten",
  "is_diabetic": false,
  "is_hypertensive": false,
  "has_heart_condition": false,
  "has_thyroid_disorder": false,
  "has_arthritis": false,
  "has_gastric_issues": false,
  "other_chronic_condition": "None",
  "family_history": "Grandfather had type-2 diabetes",
  "is_pregnant": false,
  "due_date": null,
  "is_breastfeeding": false,
  "current_trimester": null
}
```

---

### 7. Update User Profile
* **Endpoint:** `PUT /api/integration/profile/` (Full update) or `PATCH /api/integration/profile/` (Partial update)
* **Authentication:** JWT Bearer (Required)
* **Description:** Updates the patient's physical parameters and medical history flags.

#### Request Body Example (`PATCH`):
```json
{
  "weight_kg": 70.5,
  "is_diabetic": true
}
```

#### Success Response (`200 OK`):
Returns the updated profile JSON matching the `GET` profile response format.

---

### 8. List/Add/Update Lab Reports (Health Profile / Bio-Markers)
Use these endpoints to log and track detailed biological reports over time, which display on the Health Dashboard (e.g. sugar levels, HbA1c, lipid profile, kidney/liver enzymes, and thyroid).

* **Endpoints:**
  * `GET /api/integration/lab-reports/` (List all reports of the user)
  * `POST /api/integration/lab-reports/` (Add a new lab report)
  * `GET /api/integration/lab-reports/<id>/` (Get specific report details)
  * `PUT /api/integration/lab-reports/<id>/` (Update specific report)
  * `PATCH /api/integration/lab-reports/<id>/` (Partially update report)
  * `DELETE /api/integration/lab-reports/<id>/` (Delete report record)
* **Authentication:** JWT Bearer (Required)
* **Description:** Manages the chronological history of user biomarker trends. For file uploads, submit using `multipart/form-data`.

#### POST/PUT Request Fields:
```json
{
  "report_date": "2026-05-24", // YYYY-MM-DD
  "weight_kg": 72.0,
  "height_cm": 175.5,
  "waist_circumference_cm": 88.0,
  "blood_pressure_systolic": 120,
  "blood_pressure_diastolic": 80,
  
  // Blood sugar indicators
  "fasting_blood_sugar": 95.0, // mg/dL
  "postprandial_sugar": 135.0, // mg/dL
  "hba1c": 5.6, // %
  
  // Lipids
  "ldl_cholesterol": 100.0,
  "hdl_cholesterol": 50.0,
  "triglycerides": 140.0,
  
  // Inflammatory
  "crp": 0.8,
  "esr": 10.0,
  
  // Kidney & Liver
  "uric_acid": 5.5,
  "creatinine": 0.9,
  "urea": 25.0,
  "alt": 30.0,
  "ast": 25.0,
  
  // Vitamins & Hormones
  "vitamin_d3": 35.0,
  "vitamin_b12": 450.0,
  "tsh": 2.1,
  
  // Optional PDF report file (Use multipart/form-data upload)
  "report_file": null
}
```

#### Success Response Example (`GET /api/integration/lab-reports/`):
```json
[
  {
    "id": 12,
    "user": "John Doe",
    "report_date": "2026-05-24",
    "report_file": "https://res.cloudinary.com/your-cloud/image/upload/reports/files/sample.pdf",
    "weight_kg": 72.0,
    "height_cm": 175.5,
    "waist_circumference_cm": 88.0,
    "blood_pressure_systolic": 120,
    "blood_pressure_diastolic": 80,
    "fasting_blood_sugar": 95.0,
    "postprandial_sugar": 135.0,
    "hba1c": 5.6,
    "ldl_cholesterol": 100.0,
    "hdl_cholesterol": 50.0,
    "triglycerides": 140.0,
    "crp": 0.8,
    "esr": 10.0,
    "uric_acid": 5.5,
    "creatinine": 0.9,
    "urea": 25.0,
    "alt": 30.0,
    "ast": 25.0,
    "vitamin_d3": 35.0,
    "vitamin_b12": 450.0,
    "tsh": 2.1
  }
]
```

---

### 9. View Active Diet Plan
* **Endpoint:** `GET /api/integration/diet/`
* **Authentication:** JWT Bearer (Required)
* **Description:** Retrieves the active or nutritionist-approved/generated diet plan for the patient. Requires an active subscription plan to access.

#### Success Response (`200 OK`):
```json
{
  "status_code": "APPROVED", // "PENDING", "APPROVED", "REJECTED", "GENERATING", "FAILED"
  "message": "Diet plan status: Approved.",
  "plan_data": {
    "id": 105,
    "user": 42,
    "user_full_name": "John Doe",
    "for_week_starting": "2026-05-24",
    "meals": {
      "Day 1": {
        "Early-Morning": {
          "food_name": "Warm water with lemon (250 ml)",
          "quantity": "250 ml",
          "Gram_Equivalent": 250,
          "Calories": 8,
          "Protein": 0.2,
          "Carbs": 2.5,
          "Fats": 0,
          "Sugar": 0.5,
          "Fiber": 0.3
        },
        "Breakfast": {
          "food_name": "2 Vegetable Idlis with Mint Chutney",
          "quantity": "2 idlis",
          "Gram_Equivalent": 120,
          "Calories": 160,
          "Protein": 4.5,
          "Carbs": 32,
          "Fats": 1.2,
          "Sugar": 1.1,
          "Fiber": 2.4
        },
        "Mid-Morning Snack": { "food_name": "1 Apple", "quantity": "1 medium", "Gram_Equivalent": 150, "Calories": 95, "Protein": 0.5, "Carbs": 25, "Fats": 0.3, "Sugar": 19, "Fiber": 4.4 },
        "Lunch": { "food_name": "Brown Rice (1 cup) + Dal (1 cup) + Mixed Salad", "quantity": "1 bowl", "Gram_Equivalent": 350, "Calories": 380, "Protein": 12, "Carbs": 65, "Fats": 4.5, "Sugar": 2.1, "Fiber": 7.8 },
        "Afternoon Snack": { "food_name": "Roasted Chana (30g)", "quantity": "30 g", "Gram_Equivalent": 30, "Calories": 110, "Protein": 6, "Carbs": 18, "Fats": 1.8, "Sugar": 0.8, "Fiber": 4.8 },
        "Dinner": { "food_name": "Paneer Bhurji (100g) with 1 Whole Wheat Roti", "quantity": "1 serving", "Gram_Equivalent": 180, "Calories": 340, "Protein": 18, "Carbs": 28, "Fats": 14, "Sugar": 1.5, "Fiber": 3.6 },
        "Bedtime": { "food_name": "Warm turmeric milk (150 ml)", "quantity": "150 ml", "Gram_Equivalent": 150, "Calories": 90, "Protein": 4.8, "Carbs": 7.5, "Fats": 4.5, "Sugar": 6.8, "Fiber": 0 }
      },
      "Day 2": { ... },
      "Day 3": { ... },
      "suggestion_flags": ["promote_healthy_fats", "low_sodium"]
    },
    "status": "approved",
    "nutritionist_comment": null,
    "reviewed_by": null,
    "reviewer_full_name": null,
    "created_at": "2026-05-24T12:00:00Z",
    "updated_at": "2026-05-24T12:05:00Z"
  }
}
```
