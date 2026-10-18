import os
from flask import Flask, render_template
import mysql.connector
from pypdf import PdfReader
import config 
from datetime import datetime, timezone
from flask import request, jsonify
import jwt
from functools import wraps
from flask import request, jsonify, render_template
import re
from dotenv import load_dotenv

load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

if not SECRET_KEY or not JWT_SECRET_KEY:
    raise RuntimeError("Required secret keys are missing.")

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
app.config["JWT_SECRET_KEY"] = JWT_SECRET_KEY


def get_db_connection():
    connection = mysql.connector.connect(
        host=config.DB_HOST,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        use_pure=True
    )
    return connection


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/register-page")
def register_page():
    return render_template("register.html")
@app.route("/login-page")
def login_page():
    return render_template("login.html")
@app.route("/jobs")
def jobs_page():
    return render_template("jobs.html")

@app.route("/test-db")
def test_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT DATABASE();")
        result = cursor.fetchone()

        cursor.close()
        conn.close()

        return f"Connected to database: {result[0]}"

    except Exception as e:
        return f"Error: {e}" 
    @app.route("/login-page")
    def login_page():
        return render_template("login.html")


@app.route("/dashboard")
def dashboard_page():
    return render_template("dashboard.html")

@app.route("/applications")
def applications_page():
    return render_template("applications.html")


@app.route("/dashboard-data", methods=["GET"])
def dashboard_data():
    token = request.headers.get("Authorization", "")

    if not token.startswith("Bearer "):
        return jsonify({
            "success": False,
            "message": "Authentication required."
        }), 401

    token = token[7:]

    try:
        payload = jwt.decode(
            token,
            app.config["JWT_SECRET_KEY"],
            algorithms=["HS256"]
        )

        if payload.get("exp", 0) <= datetime.now(timezone.utc).timestamp():
            return jsonify({
                "success": False,
                "message": "Session expired. Please log in again."
            }), 401

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT user_id, name, email FROM users WHERE user_id = %s",
            (payload["user_id"],)
        )
        user = cursor.fetchone()

        cursor.close()
        connection.close()

        if not user:
            return jsonify({
                "success": False,
                "message": "User not found."
            }), 404

        return jsonify({
            "success": True,
            "user": user
        }), 200

    except jwt.InvalidTokenError:
        return jsonify({
            "success": False,
            "message": "Invalid or expired token."
        }), 401

    except Exception:
        app.logger.exception("Dashboard request failed")
        return jsonify({
            "success": False,
            "message": "Unable to load dashboard."
        }), 500
@app.route("/api/jobs", methods=["GET"])
def search_jobs():

    try:
        title = request.args.get("title", "").strip()
        company = request.args.get("company", "").strip()
        location = request.args.get("location", "").strip()
        skills = request.args.get("skills", "").strip()

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT
                job_id,
                title,
                company,
                location,
                required_skills,
                description,
                salary,
                created_at
            FROM jobs
            WHERE 1=1
        """

        values = []

        # Search by job title
        if title:
            query += " AND title LIKE %s"
            values.append(f"%{title}%")

        # Search by company
        if company:
            query += " AND company LIKE %s"
            values.append(f"%{company}%")

        # Search by location
        if location:
            query += " AND location LIKE %s"
            values.append(f"%{location}%")

        # Search by skills
        if skills:
            query += " AND required_skills LIKE %s"
            values.append(f"%{skills}%")

        query += " ORDER BY created_at DESC"

        cursor.execute(query, tuple(values))

        jobs = cursor.fetchall()

        cursor.close()
        connection.close()

        return jsonify({
            "success": True,
            "jobs": jobs
        }), 200

    except Exception as e:

        app.logger.exception("Job search failed")

        return jsonify({
            "success": False,
            "message": "Unable to search jobs."
        }), 500
# =========================================================
# RESUME UPLOAD
# =========================================================

import os
from werkzeug.utils import secure_filename


@app.route("/resume")
def resume_page():
    return render_template("resume.html")


@app.route("/upload-resume", methods=["POST"])
def upload_resume():

    try:

        # Check JWT token
        token = request.headers.get("Authorization", "")

        if not token.startswith("Bearer "):
            return jsonify({
                "success": False,
                "message": "Authentication required."
            }), 401

        token = token[7:]

        try:
            payload = jwt.decode(
                token,
                app.config["JWT_SECRET_KEY"],
                algorithms=["HS256"]
            )
        except jwt.InvalidTokenError:
            return jsonify({
                "success": False,
                "message": "Invalid or expired token."
            }), 401

        user_id = payload.get("user_id")

        if not user_id:
            return jsonify({
                "success": False,
                "message": "Invalid user information."
            }), 401

        # Check uploaded file
        if "resume" not in request.files:
            return jsonify({
                "success": False,
                "message": "Please select a resume."
            }), 400

        file = request.files["resume"]

        if file.filename == "":
            return jsonify({
                "success": False,
                "message": "Please select a resume."
            }), 400

        # Check file extension
        filename = secure_filename(file.filename)

        if not filename.lower().endswith(".pdf"):
            return jsonify({
                "success": False,
                "message": "Only PDF files are allowed."
            }), 400

        # Check file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)

        if file_size > config.MAX_FILE_SIZE:
            return jsonify({
                "success": False,
                "message": "Resume size must be less than 5 MB."
            }), 400

        # Create upload folder if it doesn't exist
        upload_folder = config.UPLOAD_FOLDER

        os.makedirs(upload_folder, exist_ok=True)

        # Create unique filename
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

        new_filename = f"user_{user_id}_{timestamp}_{filename}"

        file_path = os.path.join(
            upload_folder,
            new_filename
        )

        # Save file
        file.save(file_path)

        # Save information in database
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO resumes
            (
                user_id,
                file_name,
                file_path
            )
            VALUES (%s, %s, %s)
            """,
            (
                user_id,
                filename,
                file_path
            )
        )

        connection.commit()

        cursor.close()
        connection.close()

        return jsonify({
            "success": True,
            "message": "Resume uploaded successfully."
        }), 201

    except Exception as e:

        app.logger.exception("Resume upload failed")

        return jsonify({
            "success": False,
            "message": "Unable to upload resume."
        }), 500
# =========================================================
# RESUME SKILL EXTRACTION
# =========================================================

COMMON_SKILLS = [
    "Python",
    "Java",
    "C",
    "C++",
    "C#",
    "JavaScript",
    "HTML",
    "CSS",
    "React",
    "Angular",
    "Node.js",
    "Flask",
    "Django",
    "Spring Boot",
    "MySQL",
    "SQL",
    "MongoDB",
    "PostgreSQL",
    "REST API",
    "Git",
    "GitHub",
    "Docker",
    "AWS",
    "Azure",
    "Power BI",
    "Excel",
    "Pandas",
    "NumPy",
    "Machine Learning",
    "Data Analysis",
    "Artificial Intelligence"
]


def extract_skills_from_pdf(file_path):

    reader = PdfReader(file_path)

    full_text = ""

    for page in reader.pages:

        text = page.extract_text()

        if text:
            full_text += " " + text

    text_lower = full_text.lower()

    found_skills = []

    for skill in COMMON_SKILLS:

        if skill.lower() in text_lower:

            found_skills.append(skill)

    return found_skills
@app.route("/analyze-resume-page")
def analyze_resume_page():
    return render_template("analyze_resume.html")


@app.route("/analyze-resume", methods=["GET"])
def analyze_resume():

    try:

        token = request.headers.get("Authorization", "")

        if not token.startswith("Bearer "):
            return jsonify({
                "success": False,
                "message": "Authentication required."
            }), 401

        token = token[7:]

        try:

            payload = jwt.decode(
                token,
                app.config["JWT_SECRET_KEY"],
                algorithms=["HS256"]
            )

        except jwt.InvalidTokenError:

            return jsonify({
                "success": False,
                "message": "Invalid or expired token."
            }), 401

        user_id = payload.get("user_id")

        connection = get_db_connection()

        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                resume_id,
                file_name,
                file_path,
                uploaded_at
            FROM resumes
            WHERE user_id = %s
            ORDER BY uploaded_at DESC
            LIMIT 1
            """,
            (user_id,)
        )

        resume = cursor.fetchone()

        cursor.close()
        connection.close()

        if not resume:

            return jsonify({
                "success": False,
                "message": "No resume found. Please upload a resume first."
            }), 404

        skills = extract_skills_from_pdf(
            resume["file_path"]
        )

        return jsonify({
            "success": True,
            "file_name": resume["file_name"],
            "skills": skills
        }), 200

    except Exception:

        app.logger.exception("Resume analysis failed")

        return jsonify({
            "success": False,
            "message": "Unable to analyze resume."
        }), 500 
# =========================================================
# JOB RECOMMENDATIONS
# =========================================================

@app.route("/recommendations")
def recommendations_page():
    return render_template("recommendations.html")


@app.route("/api/recommendations", methods=["GET"])
def get_recommendations():

    try:
        # -------------------------------------------------
        # Check login token
        # -------------------------------------------------

        token = request.headers.get("Authorization", "")

        if not token.startswith("Bearer "):
            return jsonify({
                "success": False,
                "message": "Authentication required."
            }), 401

        token = token[7:]

        try:
            payload = jwt.decode(
                token,
                app.config["JWT_SECRET_KEY"],
                algorithms=["HS256"]
            )

        except jwt.InvalidTokenError:
            return jsonify({
                "success": False,
                "message": "Invalid or expired token."
            }), 401

        user_id = payload.get("user_id")

        if not user_id:
            return jsonify({
                "success": False,
                "message": "Invalid user information."
            }), 401

        # -------------------------------------------------
        # Get user's latest resume
        # -------------------------------------------------

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                file_path
            FROM resumes
            WHERE user_id = %s
            ORDER BY uploaded_at DESC
            LIMIT 1
            """,
            (user_id,)
        )

        resume = cursor.fetchone()

        if not resume:
            cursor.close()
            connection.close()

            return jsonify({
                "success": False,
                "message": "Please upload a resume first."
            }), 404

        # -------------------------------------------------
        # Extract skills from resume
        # -------------------------------------------------

        skills = extract_skills_from_pdf(
            resume["file_path"]
        )

        if not skills:
            cursor.close()
            connection.close()

            return jsonify({
                "success": True,
                "skills": [],
                "recommendations": []
            }), 200

        # -------------------------------------------------
        # Get all jobs
        # -------------------------------------------------

        cursor.execute(
            """
            SELECT
                job_id,
                title,
                company,
                location,
                required_skills,
                description,
                salary
            FROM jobs
            """
        )

        jobs = cursor.fetchall()

        cursor.close()
        connection.close()

        # -------------------------------------------------
        # Calculate skill match
        # -------------------------------------------------

        recommendations = []

        user_skills = {
            skill.lower().strip()
            for skill in skills
        }

        for job in jobs:

            required_skills_text = (
                job.get("required_skills") or ""
            )

            required_skills = [
                skill.strip()
                for skill in required_skills_text.split(",")
                if skill.strip()
            ]

            if not required_skills:
                continue

            matched_skills = []

            for required_skill in required_skills:

                required_lower = (
                    required_skill.lower().strip()
                )

                # Exact or partial skill match
                for user_skill in user_skills:

                    if (
                        required_lower in user_skill
                        or user_skill in required_lower
                    ):
                        matched_skills.append(
                            required_skill
                        )
                        break

            matched_skills = list(
                dict.fromkeys(matched_skills)
            )

            match_percentage = round(
                (
                    len(matched_skills)
                    / len(required_skills)
                ) * 100
            )

            # Only recommend jobs with a match
            if match_percentage > 0:

                job["match_percentage"] = (
                    match_percentage
                )

                recommendations.append(job)

        # -------------------------------------------------
        # Highest matches first
        # -------------------------------------------------

        recommendations.sort(
            key=lambda job:
                job["match_percentage"],
            reverse=True
        )

        # Return top 10 recommendations
        recommendations = recommendations[:10]

        return jsonify({
            "success": True,
            "skills": skills,
            "recommendations": recommendations
        }), 200

    except Exception:

        app.logger.exception(
            "Job recommendation failed"
        )

        return jsonify({
            "success": False,
            "message": "Unable to generate recommendations."
        }), 500
    # =========================================================
# APPLY FOR JOB
# =========================================================

@app.route("/apply/<int:job_id>", methods=["POST"])
def apply_for_job(job_id):

    try:
        # -------------------------------------------------
        # Check login token
        # -------------------------------------------------

        token = request.headers.get("Authorization", "")

        if not token.startswith("Bearer "):
            return jsonify({
                "success": False,
                "message": "Authentication required."
            }), 401

        token = token[7:]

        try:
            payload = jwt.decode(
                token,
                app.config["JWT_SECRET_KEY"],
                algorithms=["HS256"]
            )

        except jwt.InvalidTokenError:
            return jsonify({
                "success": False,
                "message": "Invalid or expired token."
            }), 401

        user_id = payload.get("user_id")

        if not user_id:
            return jsonify({
                "success": False,
                "message": "Invalid user information."
            }), 401

        # -------------------------------------------------
        # Connect to database
        # -------------------------------------------------

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # -------------------------------------------------
        # Check whether job exists
        # -------------------------------------------------

        cursor.execute(
            """
            SELECT job_id, title, company
            FROM jobs
            WHERE job_id = %s
            """,
            (job_id,)
        )

        job = cursor.fetchone()

        if not job:
            cursor.close()
            connection.close()

            return jsonify({
                "success": False,
                "message": "Job not found."
            }), 404

        # -------------------------------------------------
        # Check whether user already applied
        # -------------------------------------------------

        cursor.execute(
            """
            SELECT application_id
            FROM applications
            WHERE user_id = %s
            AND job_id = %s
            """,
            (user_id, job_id)
        )

        existing_application = cursor.fetchone()

        if existing_application:

            cursor.close()
            connection.close()

            return jsonify({
                "success": False,
                "message": "You have already applied for this job."
            }), 409

        # -------------------------------------------------
        # Create application
        # -------------------------------------------------

        cursor.execute(
            """
            INSERT INTO applications
            (user_id, job_id, status)
            VALUES (%s, %s, %s)
            """,
            (user_id, job_id, "Applied")
        )

        connection.commit()

        cursor.close()
        connection.close()

        return jsonify({
            "success": True,
            "message": "Application submitted successfully.",
            "job": {
                "job_id": job["job_id"],
                "title": job["title"],
                "company": job["company"]
            }
        }), 201

    except Exception:

        app.logger.exception(
            "Job application failed"
        )

        return jsonify({
            "success": False,
            "message": "Unable to submit application."
        }), 500
@app.route("/api/applications", methods=["GET"])
def get_applications():

    try:
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({
                "success": False,
                "message": "Authentication required."
            }), 401

        token = auth_header.split(" ")[1]

        try:
            decoded = jwt.decode(
                token,
                app.config["JWT_SECRET_KEY"],
                algorithms=["HS256"]
            )

            user_id = decoded["user_id"]

        except Exception:
            return jsonify({
                "success": False,
                "message": "Invalid or expired token."
            }), 401


        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)


        cursor.execute("""
            SELECT
                a.application_id,
                a.job_id,
                a.applied_at,
                a.status,
                j.title,
                j.company,
                j.location
            FROM applications a
            JOIN jobs j
                ON a.job_id = j.job_id
            WHERE a.user_id = %s
            ORDER BY a.applied_at DESC
        """, (user_id,))


        applications = cursor.fetchall()


        cursor.close()
        conn.close()


        return jsonify({
            "success": True,
            "applications": applications
        })


    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

# =========================================================
# ADMIN AUTHORIZATION
# =========================================================

def admin_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        parts = auth_header.split()

        if len(parts) != 2 or parts[0].lower() != "bearer":
            return jsonify({
                "success": False,
                "message": "Please log in first."
            }), 401

        connection = None
        cursor = None

        try:
            token = parts[1]

            payload = jwt.decode(
                token,
                app.config["JWT_SECRET_KEY"],
                algorithms=["HS256"]
            )

            user_id = payload.get("user_id")

            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            # Check the CURRENT database role, not just the token.
            cursor.execute(
                "SELECT role FROM users WHERE user_id = %s",
                (user_id,)
            )
            user = cursor.fetchone()

            if not user:
                return jsonify({
                    "success": False,
                    "message": "User not found."
                }), 401

            if user["role"] != "admin":
                return jsonify({
                    "success": False,
                    "message": "Admin access required."
                }), 403

            return function(*args, **kwargs)

        except jwt.ExpiredSignatureError:
            return jsonify({
                "success": False,
                "message": "Session expired. Please log in again."
            }), 401

        except jwt.InvalidTokenError:
            return jsonify({
                "success": False,
                "message": "Invalid login token."
            }), 401

        except Exception:
            app.logger.exception("Admin authorization failed")
            return jsonify({
                "success": False,
                "message": "Unable to verify admin access."
            }), 500

        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    return wrapper


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin")
def admin_page():
    return render_template("admin.html")
@app.route("/admin/jobs")
def admin_manage_jobs_page():
    return render_template("manage_jobs.html")
@app.route("/admin/applications")
def admin_manage_applications_page():
    return render_template("manage_applications.html")
@app.route("/profile")
def profile_page():
    return render_template("profile.html")
# =========================================================
# ADMIN STATISTICS API
# =========================================================

@app.route("/api/admin/stats")
@admin_required
def admin_stats():
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("SELECT COUNT(*) AS total FROM users")
        total_users = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) AS total FROM jobs")
        total_jobs = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) AS total FROM applications")
        total_applications = cursor.fetchone()["total"]

        return jsonify({
            "success": True,
            "users": total_users,
            "jobs": total_jobs,
            "applications": total_applications
        })

    except Exception:
        app.logger.exception("Failed to load admin statistics")
        return jsonify({
            "success": False,
            "message": "Could not load dashboard statistics."
        }), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

# =========================================================
# ADMIN: MANAGE JOBS
# =========================================================

@app.route("/api/admin/jobs", methods=["GET"])
@admin_required
def admin_get_jobs():
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT job_id, title, company, location,
                   required_skills, description, salary, created_at
            FROM jobs
            ORDER BY created_at DESC
        """)

        jobs = cursor.fetchall()

        for job in jobs:
            if job.get("created_at"):
                job["created_at"] = job["created_at"].isoformat()

        return jsonify({
            "success": True,
            "jobs": jobs
        }), 200

    except Exception:
        app.logger.exception("Failed to load admin jobs")
        return jsonify({
            "success": False,
            "message": "Unable to load jobs."
        }), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.route("/api/admin/jobs", methods=["POST"])
@admin_required
def admin_add_job():
    data = request.get_json(silent=True) or {}

    title = str(data.get("title") or "").strip()
    company = str(data.get("company") or "").strip()
    location = str(data.get("location") or "").strip()
    required_skills = str(data.get("required_skills") or "").strip()
    description = str(data.get("description") or "").strip()
    salary = str(data.get("salary") or "").strip()

    if not title or not company or not location:
        return jsonify({
            "success": False,
            "message": "Job title, company, and location are required."
        }), 400

    if len(title) > 150 or len(company) > 150 or len(location) > 150:
        return jsonify({
            "success": False,
            "message": "Title, company, and location must be at most 150 characters."
        }), 400

    if len(salary) > 100:
        return jsonify({
            "success": False,
            "message": "Salary must be at most 100 characters."
        }), 400

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO jobs
                (title, company, location, required_skills, description, salary)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            title,
            company,
            location,
            required_skills or None,
            description or None,
            salary or None
        ))

        connection.commit()
        new_job_id = cursor.lastrowid

        return jsonify({
            "success": True,
            "message": "Job added successfully.",
            "job_id": new_job_id
        }), 201

    except Exception:
        if connection:
            connection.rollback()

        app.logger.exception("Failed to add admin job")
        return jsonify({
            "success": False,
            "message": "Unable to add job."
        }), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.route("/api/admin/jobs/<int:job_id>", methods=["DELETE"])
@admin_required
def admin_delete_job(job_id):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            "SELECT job_id FROM jobs WHERE job_id = %s",
            (job_id,)
        )

        if not cursor.fetchone():
            return jsonify({
                "success": False,
                "message": "Job not found."
            }), 404

        # Preserve existing application records. If applications
        # reference this job, ask the admin to keep the job instead.
        cursor.execute(
            "SELECT COUNT(*) FROM applications WHERE job_id = %s",
            (job_id,)
        )
        application_count = cursor.fetchone()[0]

        if application_count > 0:
            return jsonify({
                "success": False,
                "message": (
                    "This job has existing applications and cannot be "
                    "deleted. Keeping it preserves application history."
                )
            }), 409

        cursor.execute(
            "DELETE FROM jobs WHERE job_id = %s",
            (job_id,)
        )
        connection.commit()

        return jsonify({
            "success": True,
            "message": "Job deleted successfully."
        }), 200

    except Exception:
        if connection:
            connection.rollback()

        app.logger.exception("Failed to delete admin job")
        return jsonify({
            "success": False,
            "message": "Unable to delete job."
        }), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

# =========================================================
# ADMIN: MANAGE APPLICATIONS
# =========================================================

@app.route("/api/admin/applications", methods=["GET"])
@admin_required
def admin_get_applications():
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                a.application_id,
                a.user_id,
                a.job_id,
                a.applied_at,
                a.status,
                u.name AS applicant_name,
                u.email AS applicant_email,
                j.title AS job_title,
                j.company AS company,
                j.location AS job_location
            FROM applications a
            JOIN users u ON a.user_id = u.user_id
            JOIN jobs j ON a.job_id = j.job_id
            ORDER BY a.applied_at DESC
        """)

        applications = cursor.fetchall()

        for application in applications:
            if application.get("applied_at"):
                application["applied_at"] = (
                    application["applied_at"].isoformat()
                )

        return jsonify({
            "success": True,
            "applications": applications
        }), 200

    except Exception:
        app.logger.exception("Failed to load admin applications")
        return jsonify({
            "success": False,
            "message": "Unable to load applications."
        }), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.route(
    "/api/admin/applications/<int:application_id>",
    methods=["PATCH"]
)
@admin_required
def admin_update_application(application_id):
    data = request.get_json(silent=True) or {}
    status = str(data.get("status") or "").strip()

    allowed_statuses = {
        "Applied",
        "Under Review",
        "Shortlisted",
        "Selected",
        "Rejected"
    }

    if status not in allowed_statuses:
        return jsonify({
            "success": False,
            "message": "Please select a valid application status."
        }), 400

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE applications
            SET status = %s
            WHERE application_id = %s
        """, (status, application_id))

        if cursor.rowcount == 0:
            cursor.execute("""
                SELECT application_id, status
                FROM applications
                WHERE application_id = %s
            """, (application_id,))

            existing = cursor.fetchone()

            if not existing:
                return jsonify({
                    "success": False,
                    "message": "Application not found."
                }), 404

        connection.commit()

        return jsonify({
            "success": True,
            "message": "Application status updated successfully."
        }), 200

    except Exception:
        if connection:
            connection.rollback()

        app.logger.exception("Failed to update application status")
        return jsonify({
            "success": False,
            "message": "Unable to update application status."
        }), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.route("/api/profile", methods=["GET"])
def get_profile():
    import jwt
    from flask import request, jsonify

    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        return jsonify({"message": "Please log in."}), 401

    token = auth_header.split(" ", 1)[1]

    try:
        payload = jwt.decode(
            token,
            app.config["JWT_SECRET_KEY"],
            algorithms=["HS256"]
        )
        user_id = payload.get("user_id")

        if not user_id:
            return jsonify({"message": "Invalid login token."}), 401

    except jwt.InvalidTokenError:
        return jsonify({"message": "Invalid or expired token."}), 401

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT user_id, name, email, mobile, qualification, skills
            FROM users
            WHERE user_id = %s
            """,
            (user_id,)
        )

        user = cursor.fetchone()

        if not user:
            return jsonify({"message": "User not found."}), 404

        return jsonify({
            "user_id": user[0],
            "name": user[1],
            "email": user[2],
            "mobile": user[3],
            "qualification": user[4],
            "skills": user[5]
        }), 200

    except Exception:
        app.logger.exception("Failed to load user profile")
        return jsonify({"message": "Could not load profile."}), 500

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()


@app.route("/api/profile", methods=["PATCH"])
def update_profile():
    import jwt
    from flask import request, jsonify

    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        return jsonify({"message": "Please log in."}), 401

    token = auth_header.split(" ", 1)[1]

    try:
        payload = jwt.decode(
            token,
            app.config["JWT_SECRET_KEY"],
            algorithms=["HS256"]
        )
        user_id = payload.get("user_id")

        if not user_id:
            return jsonify({"message": "Invalid login token."}), 401

    except jwt.InvalidTokenError:
        return jsonify({"message": "Invalid or expired token."}), 401

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"message": "Invalid request data."}), 400

    name = data.get("name")
    mobile = data.get("mobile", "")
    qualification = data.get("qualification", "")
    skills = data.get("skills", "")

    if not isinstance(name, str) or not name.strip():
        return jsonify({"message": "Name is required."}), 400

    if not all(
        isinstance(value, str)
        for value in (mobile, qualification, skills)
    ):
        return jsonify({"message": "Invalid profile field values."}), 400

    name = name.strip()
    mobile = mobile.strip()
    qualification = qualification.strip()
    skills = skills.strip()

    if len(name) > 100 or len(mobile) > 20:
        return jsonify({"message": "Name or mobile number is too long."}), 400

    if len(qualification) > 200 or len(skills) > 3000:
        return jsonify({"message": "Qualification or skills is too long."}), 400

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            UPDATE users
            SET name = %s,
                mobile = %s,
                qualification = %s,
                skills = %s
            WHERE user_id = %s
            """,
            (name, mobile, qualification, skills, user_id)
        )

        if cursor.rowcount == 0:
            cursor.execute(
                "SELECT user_id FROM users WHERE user_id = %s",
                (user_id,)
            )

            if not cursor.fetchone():
                return jsonify({"message": "User not found."}), 404

        connection.commit()

        return jsonify({
            "message": "Profile updated successfully."
        }), 200

    except Exception:
        if connection is not None and connection.is_connected():
            connection.rollback()

        app.logger.exception("Failed to update user profile")
        return jsonify({"message": "Could not update profile."}), 500

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()



from app import auth