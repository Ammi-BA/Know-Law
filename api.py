"""
=============================================================================
api.py  —  KnowLaw AI  |  REST API Layer for Postman E2E Testing
=============================================================================
This file creates a lightweight Flask REST API that wraps the existing
business-logic functions in auth.py and vault_manager.py.

It does NOT change any existing code. It simply exposes the functions as
HTTP endpoints so they can be tested end-to-end in Postman.

HOW TO RUN:
    pip install flask
    python api.py

The server will start at:  http://localhost:5000
=============================================================================
"""

from flask import Flask, request, jsonify
import sys
import os

# Make sure Python can find auth.py and vault_manager.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import auth
import vault_manager

app = Flask(__name__)


# =============================================================================
# HELPERS
# =============================================================================

def ok(data: dict, status: int = 200):
    """Return a successful JSON response."""
    return jsonify({"success": True, **data}), status


def err(message: str, status: int = 400):
    """Return a failure JSON response."""
    return jsonify({"success": False, "error": message}), status


# =============================================================================
# SCENARIO 1 — USER REGISTRATION & LOGIN
# =============================================================================

@app.route("/api/register", methods=["POST"])
def register():
    """
    Register a new Citizen or Lawyer.

    Body (JSON):
    {
        "role":      "Citizen" | "Lawyer",
        "full_name": "Ahmed Ali",
        "email":     "ahmed@test.com",
        "password":  "securepass123",
        "phone":     "0101234567",
        "age":       30,
        "city":      "Cairo",
        "address":   "12 Tahrir St",
        "specialty": "Criminal Law",   <-- Lawyers only
        "bio":       "10 years exp."   <-- Lawyers only
    }
    """
    data = request.get_json(force=True, silent=True)
    if not data:
        return err("Request body must be JSON.")

    required = ["role", "full_name", "email", "password", "phone", "age", "city", "address"]
    for field in required:
        if field not in data:
            return err(f"Missing required field: '{field}'")

    role = data["role"]
    if role not in ("Citizen", "Lawyer"):
        return err("Role must be 'Citizen' or 'Lawyer'.")

    success = auth.register_user(
        role       = role,
        full_name  = data["full_name"],
        email      = data["email"],
        password   = data["password"],
        phone      = data["phone"],
        age        = data["age"],
        city       = data["city"],
        address    = data["address"],
        specialty  = data.get("specialty"),
        bio        = data.get("bio"),
    )

    if success:
        status_msg = "Pending admin approval" if role == "Lawyer" else "Approved"
        return ok({
            "message":        f"{role} registered successfully.",
            "verified_status": status_msg
        }, 201)
    else:
        return err("Email already registered. Please use a different email.", 409)


@app.route("/api/login", methods=["POST"])
def login():
    """
    Login with email and password.

    Body (JSON):
    {
        "email":    "ahmed@test.com",
        "password": "securepass123"
    }
    """
    data = request.get_json(force=True, silent=True)
    if not data:
        return err("Request body must be JSON.")

    email    = data.get("email", "")
    password = data.get("password", "")

    if not email or not password:
        return err("Both 'email' and 'password' are required.")

    user = auth.login_user(email, password)
    if user:
        return ok({
            "message":   "Login successful.",
            "user_id":   user["id"],
            "role":      user["role"],
            "full_name": user["full_name"],
            "status":    user["status"],
        })
    else:
        return err("Invalid email or password.", 401)


# =============================================================================
# SCENARIO 2 — LAWYER DIRECTORY SEARCH
# =============================================================================

@app.route("/api/lawyers", methods=["GET"])
def get_lawyers():
    """
    Get all approved lawyers. Supports optional query filters.

    Query params (all optional):
        city      = Cairo
        specialty = Criminal Law
        search    = Ahmed          <-- partial name search
    """
    city      = request.args.get("city")
    specialty = request.args.get("specialty")
    search    = request.args.get("search")

    lawyers = auth.get_approved_lawyers(city=city, specialty=specialty, search=search)
    return ok({
        "count":   len(lawyers),
        "lawyers": lawyers
    })


# =============================================================================
# SCENARIO 3 — ADMIN: LAWYER APPROVAL WORKFLOW
# =============================================================================

@app.route("/api/admin/pending-lawyers", methods=["GET"])
def pending_lawyers():
    """
    Get all lawyers waiting for admin approval.
    (In a real app this would require an admin auth token — simplified here.)
    """
    pending = auth.get_pending_lawyers()
    return ok({
        "count":   len(pending),
        "lawyers": pending
    })


@app.route("/api/admin/approve/<int:user_id>", methods=["POST"])
def approve_lawyer(user_id):
    """
    Approve a pending lawyer by their user ID.

    URL:  POST /api/admin/approve/5
    """
    auth.approve_lawyer(user_id)
    return ok({"message": f"Lawyer (ID: {user_id}) has been approved successfully."})


@app.route("/api/admin/reject/<int:user_id>", methods=["DELETE"])
def reject_lawyer(user_id):
    """
    Reject and remove a pending lawyer by their user ID.

    URL:  DELETE /api/admin/reject/5
    """
    auth.reject_lawyer(user_id)
    return ok({"message": f"Lawyer (ID: {user_id}) has been rejected and removed."})


# =============================================================================
# SCENARIO 4 — APPOINTMENT BOOKING FLOW
# =============================================================================

@app.route("/api/appointments", methods=["POST"])
def book_appointment():
    """
    A citizen sends an appointment request to a lawyer.

    Body (JSON):
    {
        "citizen_id": 3,
        "lawyer_id":  7,
        "message":    "I need help with a property dispute."
    }
    """
    data = request.get_json(force=True, silent=True)
    if not data:
        return err("Request body must be JSON.")

    citizen_id = data.get("citizen_id")
    lawyer_id  = data.get("lawyer_id")
    message    = data.get("message", "").strip()

    if not citizen_id or not lawyer_id:
        return err("Both 'citizen_id' and 'lawyer_id' are required.")
    if not message:
        return err("'message' cannot be empty.")

    auth.send_appointment_request(citizen_id, lawyer_id, message)
    return ok({"message": "Appointment request sent successfully."}, 201)


@app.route("/api/appointments/lawyer/<int:lawyer_id>", methods=["GET"])
def lawyer_appointments(lawyer_id):
    """
    Get all appointment requests received by a specific lawyer.

    URL:  GET /api/appointments/lawyer/7
    """
    appointments = auth.get_lawyer_appointments(lawyer_id)
    return ok({
        "count":        len(appointments),
        "appointments": appointments
    })


@app.route("/api/appointments/citizen/<int:citizen_id>", methods=["GET"])
def citizen_appointments(citizen_id):
    """
    Get all appointment requests sent by a specific citizen.

    URL:  GET /api/appointments/citizen/3
    """
    appointments = auth.get_citizen_appointments(citizen_id)
    return ok({
        "count":        len(appointments),
        "appointments": appointments
    })


@app.route("/api/appointments/<int:appointment_id>/respond", methods=["POST"])
def respond_appointment(appointment_id):
    """
    A lawyer accepts or rejects an appointment request.

    URL:  POST /api/appointments/1/respond
    Body (JSON):
    {
        "status":   "Accepted" | "Rejected",
        "response": "Available on Thursday at 4pm."
    }
    """
    data = request.get_json(force=True, silent=True)
    if not data:
        return err("Request body must be JSON.")

    status   = data.get("status", "").strip()
    response = data.get("response", "").strip()

    if status not in ("Accepted", "Rejected"):
        return err("'status' must be 'Accepted' or 'Rejected'.")
    if not response:
        return err("'response' message cannot be empty.")

    auth.respond_to_appointment(appointment_id, status, response)
    return ok({"message": f"Appointment {appointment_id} marked as '{status}'."})


# =============================================================================
# SCENARIO 5 — PASSWORD RESET FLOW
# =============================================================================

@app.route("/api/password-reset/request", methods=["POST"])
def request_password_reset():
    """
    Request a password reset token for an email address.

    Body (JSON):
    {
        "email": "ahmed@test.com"
    }

    NOTE: In a real app the token would be emailed. Here it is returned
    in the response so you can use it directly in Postman.
    """
    data = request.get_json(force=True, silent=True)
    if not data:
        return err("Request body must be JSON.")

    email = data.get("email", "").strip().lower()
    if not email:
        return err("'email' is required.")

    token = auth.create_password_reset_token(email)
    if token:
        return ok({
            "message": "Password reset token generated successfully.",
            "token":   token,
            "note":    "Copy this token and use it in the /validate and /reset steps."
        })
    else:
        return err("No account found with that email address.", 404)


@app.route("/api/password-reset/validate", methods=["POST"])
def validate_reset_token():
    """
    Check whether a reset token is still valid (not expired, not used).

    Body (JSON):
    {
        "token": "abc123xyz..."
    }
    """
    data = request.get_json(force=True, silent=True)
    if not data:
        return err("Request body must be JSON.")

    token = data.get("token", "").strip()
    if not token:
        return err("'token' is required.")

    email = auth.validate_reset_token(token)
    if email:
        return ok({
            "message": "Token is valid.",
            "email":   email
        })
    else:
        return err("Token is invalid or has expired.", 401)


@app.route("/api/password-reset/reset", methods=["POST"])
def reset_password():
    """
    Use a valid token to set a new password.

    Body (JSON):
    {
        "token":        "abc123xyz...",
        "new_password": "mynewpassword99"
    }
    """
    data = request.get_json(force=True, silent=True)
    if not data:
        return err("Request body must be JSON.")

    token        = data.get("token", "").strip()
    new_password = data.get("new_password", "").strip()

    if not token or not new_password:
        return err("Both 'token' and 'new_password' are required.")
    if len(new_password) < 8:
        return err("New password must be at least 8 characters long.")

    success = auth.reset_password(token, new_password)
    if success:
        return ok({"message": "Password reset successfully. You can now log in with your new password."})
    else:
        return err("Token is invalid or has expired.", 401)


# =============================================================================
# SCENARIO 6 — CHAT VAULT
# =============================================================================

@app.route("/api/vault/save", methods=["POST"])
def save_chat():
    """
    Save a chat session to the vault.

    Body (JSON):
    {
        "user_id":      3,
        "session_name": "My Contract Question",
        "session_type": "chat",
        "messages": [
            {"role": "user",      "content": "What is Article 45?"},
            {"role": "assistant", "content": "Article 45 states..."}
        ]
    }
    """
    data = request.get_json(force=True, silent=True)
    if not data:
        return err("Request body must be JSON.")

    user_id      = data.get("user_id")
    session_name = data.get("session_name", "").strip()
    session_type = data.get("session_type", "chat")
    messages     = data.get("messages", [])

    if not user_id or not session_name:
        return err("'user_id' and 'session_name' are required.")
    if session_type not in ("chat", "ocr", "contract"):
        return err("'session_type' must be 'chat', 'ocr', or 'contract'.")

    vault_manager.save_chat(user_id, session_name, messages, session_type=session_type)
    return ok({"message": f"Chat session '{session_name}' saved successfully."}, 201)


@app.route("/api/vault/<int:user_id>", methods=["GET"])
def get_vault(user_id):
    """
    Get all saved chat sessions for a user.

    URL:  GET /api/vault/3?type=chat
    Query param:
        type = chat | ocr | contract   (default: chat)
    """
    session_type = request.args.get("type", "chat")
    chats = vault_manager.get_user_chats(user_id, session_type=session_type)
    return ok({
        "user_id": user_id,
        "type":    session_type,
        "count":   len(chats),
        "sessions": chats
    })


# =============================================================================
# HEALTH CHECK
# =============================================================================

@app.route("/api/health", methods=["GET"])
def health():
    """Simple health check — confirms the API is running."""
    return ok({"message": "KnowLaw API is running.", "status": "healthy"})


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  KnowLaw AI — REST API for Postman E2E Testing")
    print("  Server running at: http://localhost:5000")
    print("=" * 60)
    app.run(debug=True, port=5000)
