
from flask import request, jsonify
import bcrypt
import jwt
import os
from datetime import datetime, timedelta, timezone

from app import app, get_db_connection


# =========================================================
# REGISTER
# =========================================================

@app.route("/register", methods=["POST"])
def register():

    connection = None
    cursor = None

    try:
        data = request.get_json(silent=True) or {}

        name = data.get("name", "").strip()
        email = data.get("email", "").strip()
        mobile = data.get("mobile", "").strip()
        qualification = data.get("qualification", "").strip()
        skills = data.get("skills", "").strip()
        password = data.get("password", "")

        # Validate required fields
        if not name or not email or not mobile or not password:
            return jsonify({
                "success": False,
                "message": "Please fill all required fields."
            }), 400

        # Hash password
        password_hash = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

        # Connect to database
        connection = get_db_connection()
        cursor = connection.cursor()

        # Check for duplicate email or mobile
        cursor.execute(
            """
            SELECT user_id
            FROM users
            WHERE email = %s OR mobile = %s
            """,
            (email, mobile)
        )

        if cursor.fetchone():
            return jsonify({
                "success": False,
                "message": "Email or mobile number already registered."
            }), 409

        # New registrations are always regular users.
        # Never accept an admin role from registration input.
        cursor.execute(
            """
            INSERT INTO users
                (name, email, mobile, password_hash,
                 qualification, skills)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                name,
                email,
                mobile,
                password_hash,
                qualification,
                skills
            )
        )

        connection.commit()

        return jsonify({
            "success": True,
            "message": "Registration successful."
        }), 201

    except Exception as e:
        if connection:
            connection.rollback()

        app.logger.exception("Registration failed")

        return jsonify({
            "success": False,
            "message": "Registration failed. Please try again."
        }), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["POST"])
def login():

    connection = None
    cursor = None

    try:
        data = request.get_json(silent=True) or {}

        email = data.get("email", "").strip()
        password = data.get("password", "")

        if not email or not password:
            return jsonify({
                "success": False,
                "message": "Please enter email and password."
            }), 400

        # Connect to database
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Fetch user and role
        cursor.execute(
            """
            SELECT
                user_id,
                name,
                email,
                password_hash,
                qualification,
                skills,
                role
            FROM users
            WHERE email = %s
            """,
            (email,)
        )

        user = cursor.fetchone()

        if not user:
            return jsonify({
                "success": False,
                "message": "Invalid email or password."
            }), 401

        # Verify password
        password_correct = bcrypt.checkpw(
            password.encode("utf-8"),
            user["password_hash"].encode("utf-8")
        )

        if not password_correct:
            return jsonify({
                "success": False,
                "message": "Invalid email or password."
            }), 401

        # Create JWT containing the database role
        jwt_secret = app.config.get("JWT_SECRET_KEY") or os.getenv("JWT_SECRET_KEY")

        if not jwt_secret:
             raise RuntimeError("JWT_SECRET_KEY is not configured.")

        token = jwt.encode(
            {
                "user_id": user["user_id"],
                "email": user["email"],
                "role": user["role"],
                "exp": datetime.now(timezone.utc) + timedelta(hours=2)
            },
            jwt_secret,
            algorithm="HS256"
        )

        return jsonify({
            "success": True,
            "message": "Login successful.",
            "token": token,
            "user": {
                "user_id": user["user_id"],
                "name": user["name"],
                "email": user["email"],
                "role": user["role"]
            }
        }), 200

    except Exception:
        app.logger.exception("Login failed")

        return jsonify({
            "success": False,
            "message": "Login failed. Please try again."
        }), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
