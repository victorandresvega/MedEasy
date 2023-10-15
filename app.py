import os
import certifi
import time

from flask import Flask, render_template, request, redirect, flash, session, url_for
from flask_pymongo import PyMongo
from flask_bcrypt import Bcrypt
from appointment import Appointment
from doctor import Doctor
from patient import Patient
from event import Event
from photo import Photo
from user import User
from dotenv import load_dotenv
from bson import ObjectId
from datetime import datetime



load_dotenv()

# -- Initialization section --
app = Flask(__name__)
app.config["SECRET_KEY"] = "MedEasy"
app.config['SECURITY_PASSWORD_HASH'] = 'bcrypt'
app.config['SECURITY_PASSWORD_SALT'] = 'MedEasy'

# name of database
app.config["MONGO_DBNAME"] = "MedEasy"

# URI of database
app.config[
    'MONGO_URI'] = "mongodb+srv://MedEasy:MedEasy@cluster0.l8xpye7.mongodb.net/MedEasy"

mongo = PyMongo(app, tlsCAFile=certifi.where())
bcrypt = Bcrypt(app)

# time_slots = ["08:00am", "08:30am", "09:00am", "09:30am", "10:00am", "10:30am", "11:00am", "11:30am", "12:00pm",
#               "12:30pm", "01:00pm", "01:30pm", "02:00pm", "02:30pm", "03:00pm", "03:30pm", "04:00pm", "04:30pm"]

# doctor_ids = {"Richard Silverstein": "1234"}

@app.route("/", methods=["GET", "POST"])
@app.route("/home", methods=["GET", "POST"])
def home():
    specialties = Doctor.medicalSpecialties
    
    if request.method == "GET":
        users = mongo.db.users.find({"role": "doctor"})
        
    if request.method == "POST":
        specialty = request.form.get("doctor-specialty")
        name = request.form.get("doctor-name")
        users = Doctor.get_filtered_doctors(mongo.db, specialty, name)
        
    logged_in = "_id" in session
    return render_template('home.html', users=users, specialties=specialties, logged_in=logged_in)

@app.route("/about")
def about():
    return render_template("about.html")

@app.route('/signin', methods=['GET'])
def signinGET():
    return render_template('signin.html')

@app.route('/signin', methods=['POST'])
def signinPOST():
    email = request.form.get('email')
    password = request.form.get('password')
    user = mongo.db["users"].find_one({"email": email})

    if user and User.check_password(bcrypt, user.get('password'), password):
        session["_id"] = str(user["_id"])
        session['user_role'] = user["role"]

        flash('Login successful!', 'success')
        return redirect(url_for('home'))
    else:
        flash('Login unsuccessful. Check email and password', 'danger')
    return signinGET()


@app.route('/signup', methods=['GET'])
def signupGET():
    specialties = Doctor.medicalSpecialties
    medical_coverages = Doctor.medicalCoverages
    work_days = Doctor.daysWeek
    
    return render_template('signup.html', specialties=specialties, medical_coverages=medical_coverages, work_days= work_days)
    
@app.route('/signup', methods=['POST'])
def signupPOST():
    account_type = request.form.get('accountType')
    email = request.form.get('email')

    # Check if the email already exists in the database
    existing_user = mongo.db["users"].find_one({"email": email})

    if existing_user:
        flash('An account with that email already exists!', 'danger')
        return signupGET()

    # Continue with the rest of the signup process if email is unique
    password = request.form.get('password')

    payload = {}

    # Fields specific to the doctor role
    if account_type == "patient":
        payload["first_name"] = request.form.get('patient_first_name')
        payload["last_name"] = request.form.get('patient_last_name')
        payload["phone_number"] = request.form.get('patient_phone_number')

    if account_type == "doctor":
        payload["first_name"] = request.form.get('first_name')
        payload["last_name"] = request.form.get('last_name')
        payload["specialties"] = request.form.getlist('specialties[]')
        payload["address"] = request.form.get('address')
        payload["medical_coverages"] = request.form.getlist('medical_coverages[]')
        payload["phone_number"] = request.form.get('phone_number')
        
        schedule = {}
        schedule["work_days"] = request.form.getlist('work_days[]')

        # Convert clock_in and clock_out into epoch
        current_date = time.strftime('%Y-%m-%d')  # Getting the current date
        
        clock_in_combined = current_date + ' ' + request.form.get('clock_in')
        clock_out_combined = current_date + ' ' + request.form.get('clock_out')
        
        clock_in_time = time.mktime(time.strptime(clock_in_combined, '%Y-%m-%d %H:%M'))
        clock_out_time = time.mktime(time.strptime(clock_out_combined, '%Y-%m-%d %H:%M'))
        
        schedule["clock_in"] = clock_in_time
        schedule["clock_out"] = clock_out_time
        
        payload["schedule"] = schedule  # Add schedule to the payload

        photo_file = request.files.get('photo')
        if photo_file and photo_file.filename != '':
            photo_path = os.path.join("static/img/", photo_file.filename)
            photo_file.save(photo_path)
            encoded_photo = Photo.encodeImage(photo_path)
            os.remove(photo_path)
        else:
            encoded_photo = Photo.encodeImage("https://freesvg.org/img/abstract-user-flat-4.png") #Default image

        payload["photo"] = encoded_photo



    # Create the user with the above payload
    created_user = User.create_user(
        bcrypt, email=email, password=password, role=account_type, payload=payload, database=mongo.db)

    session['_id'] = created_user._id
    session['user_role'] = account_type
    flash('Account created!', 'success')
    return redirect(url_for('home'))


@app.route('/signout')
def signout():
    session.clear()
    flash('You have been logged out successfully!', 'success')
    return redirect(url_for('home'))


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    user_id = session.get('_id', None)
    user = User.get_user_by_id(user_id, mongo.db)
    user_appointments = list(mongo.db.appointments.find({"patient_id": ObjectId(user_id)}))


    if not user:  
        flash('User not found.', 'danger')
        return redirect(url_for('home'))

    # Convert the epoch timestamp to date and time for each appointment
    for appointment in user_appointments:
        appointment['date'] = Appointment.epoch_to_date(appointment['timestamp'])
        appointment['time'] = Appointment.epoch_to_time(appointment['timestamp'])


        doctor = mongo.db.users.find_one({"_id": appointment['doctor_id']})
        if doctor:
            appointment['doctor_name'] = doctor['payload'].get('first_name', '') + " " + doctor['payload'].get('last_name', '')
            appointment['phone'] = doctor['payload'].get('phone_number', 'N/A')
            appointment['location'] = doctor['payload'].get('address', 'N/A')
        else:
            appointment['doctor_name'] = 'N/A'
            appointment['phone'] = 'N/A'
            appointment['location'] = 'N/A'

    if user.role == "doctor":
        if request.method == 'POST':

            first_name = helper_getVal('first_name', request.form, user.payload)
            last_name = helper_getVal('last_name', request.form, user.payload)
            address = helper_getVal('address', request.form, user.payload) 
            phone_number = helper_getVal('phone_number', request.form, user.payload) 
            specialties = helper_getValList('specialties', request.form, user.payload)
            medical_coverages = helper_getValList('medical_coverages', request.form, user.payload)
            photo = helper_getVal('photo', )
            
            collection = mongo.db.users
            collection.update_one({"_id": user_id}, {
                "$set": {
                    "payload": {
                        "first_name": first_name,
                        "last_name": last_name,
                        "specialties": specialties,
                        "address": address,
                        "phone_number": phone_number,
                        "medical_coverages": medical_coverages,
                        "photo": photo
                    }
                }
            })
        else:
            photo = user.payload.get("photo")
            if photo:
                photo_data = Photo.decodeImage(photo)
            else:
                photo_data = Photo.encodeImage("https://freesvg.org/img/abstract-user-flat-4.png")

            if 'schedule' not in user.payload:
                user.payload['schedule'] = {"work_days": [], "clock_in": None, "clock_out": None}

            return render_template('doctor.html', doctor_email=user, doctor=user.payload, photo=photo_data)



    elif user.role == "patient":
        if request.method == 'POST':
            first_name = request.form.get(
                'first_name', user.payload['first_name'])
            last_name = request.form.get(
                'last_name', user.payload['last_name'])
            phone_number = request.form.get(
                'phone_number', user.payload['phone_number'])

            collection = mongo.db.users
            collection.update_one({"_id": user_id}, {
                "$set": {
                    "payload": {
                        "first_name": first_name,
                        "last_name": last_name,
                        "phone_number": phone_number,
                    }
                }
            })
            user = User.get_user_by_id(user_id, mongo.db)


        return render_template('patient.html', user=user, appointments=user_appointments)


    else:
        flash('Invalid profile type.', 'danger')
        return redirect(url_for('home'))
    
def helper_getVal(field_name, form, payload):
    return form.get(field_name, payload[field_name])

def helper_getValList(field_name, form, payload):
    if len(form.getlist(field_name)) == 0:
        return payload[field_name]
    return form.getlist(field_name)

@app.route('/profile/edit', methods=['GET', 'POST'])
def edit_profile():
    user_id = session.get('_id', None)
    user = User.get_user_by_id(user_id, mongo.db)
    
    specialties = Doctor.medicalSpecialties
    medical_coverages = Doctor.medicalCoverages
    work_days = Doctor.daysWeek

    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('home'))

    if user.role == "doctor":
        current_date = time.strftime('%Y-%m-%d')  # Fetch the current date once at the start
        
        if request.method == 'POST':
            email = request.form.get('email', user.email)
            first_name = helper_getVal('first_name', request.form, user.payload)
            last_name = helper_getVal('last_name', request.form, user.payload)
            address = helper_getVal('address', request.form, user.payload)
            phone_number = helper_getVal('phone_number', request.form, user.payload)
            specialties = helper_getValList('specialties[]', request.form, user.payload)
            medical_coverages = helper_getValList('medical_coverages[]', request.form, user.payload)
            
            clock_in_time_str = request.form.get('clock_in')
            clock_out_time_str = request.form.get('clock_out')


            clock_in_time = time_to_epoch(current_date, clock_in_time_str)
            clock_out_time = time_to_epoch(current_date, clock_out_time_str)


            work_days = request.form.getlist('work_days[]')

            # Photo handling
            photo_file = request.files.get('photo')
            if photo_file and photo_file.filename != '':
                photo_path = os.path.join("static/img/pfp", photo_file.filename)
                photo_file.save(photo_path)
                encoded_photo = Photo.encodeImage(photo_path)
                os.remove(photo_path)  # delete temp photo after encoding
                
                collection = mongo.db.users
                collection.update_one({"_id": ObjectId(user_id)}, {
                    "$set": {
                        "payload.photo": encoded_photo
                    }
                })
            else:
                encoded_photo = user.payload.get("photo", None)

            updated_payload = {
                "email": email,
                "payload.first_name": first_name,
                "payload.last_name": last_name,
                "payload.specialties": specialties,
                "payload.address": address,
                "payload.phone_number": phone_number,
                "payload.medical_coverages": medical_coverages,
                "payload.schedule.work_days": work_days,
                "payload.schedule.clock_in": clock_in_time,
                "payload.schedule.clock_out": clock_out_time,
            }

            collection = mongo.db.users
            collection.update_one({"_id": ObjectId(user_id)}, {
                "$set": updated_payload
            })

            return redirect(url_for('profile'))

        else:
            clock_in_value = user.payload.get('schedule', {}).get('clock_in', None)
            clock_out_value = user.payload.get('schedule', {}).get('clock_out', None)
            
            if clock_in_value is not None:
                clock_in_time = datetime.fromtimestamp(int(clock_in_value)).strftime('%I:%M%p')
            else:
                clock_in_time = '00:00'
                
            if clock_out_value is not None:
                clock_out_time = datetime.fromtimestamp(int(clock_out_value)).strftime('%I:%M%p')
            else:
                clock_out_time = '00:00'

        return render_template('editDoctor.html', doctor_email=user, doctor=user.payload,
                       specialties=specialties, medical_coverages=medical_coverages, work_days=work_days,
                       clock_in_time=clock_in_time, clock_out_time=clock_out_time)

    elif user.role == "patient":
        if request.method == 'POST':
            email = request.form.get('email', user.email)
            first_name = helper_getVal('first_name', request.form, user.payload)
            last_name = helper_getVal('last_name', request.form, user.payload)
            phone_number = helper_getVal('phone_number', request.form, user.payload)

            collection = mongo.db.users
            collection.update_one({"_id": ObjectId(user_id)}, {
                "$set": {
                    "email": email,
                    "payload.first_name": first_name,
                    "payload.last_name": last_name,
                    "payload.phone_number": phone_number
                }
            })

            return redirect(url_for('profile'))

        return render_template('editPatient.html', user=user)

    else:
        flash('Invalid profile type.', 'danger')
        return redirect(url_for('home'))

def helper_getVal(field_name, form, payload):
    return form.get(field_name, payload[field_name])

def helper_getValList(field_name, form, payload):
    if len(form.getlist(field_name)) == 0:
        return payload[field_name]
    return form.getlist(field_name)

def time_to_epoch(date_str, time_str, format_str='%Y-%m-%d %H:%M'):
    combined_str = date_str + ' ' + time_str
    return time.mktime(time.strptime(combined_str, format_str))


@app.template_filter('time')
def time_filter(s, format="%I:%M %p"):
    if s is None:
        return 'N/A'
    return datetime.fromtimestamp(s).strftime(format)




# @app.route("/schedule/Dr.<first_name><last_name>", methods=["GET", "POST"])
# def schedule(first_name, last_name):
#     user = mongo.db.users.find_one({"payload.first_name": first_name, "payload.last_name": last_name, "role": "doctor"})

#     user = mongo.db.users.find_one({
#      "payload.first_name": first_name, 
#      "payload.last_name": last_name, 
#      "role": "doctor"
#  })

#     if not user:
#         flash('Doctor not found.', 'danger')
#         return redirect(url_for('home'))

#     doctor = user['payload']
#     medical_plans = doctor['medical_coverages']
#     doctor_name = doctor['first_name'] + " " + doctor['last_name']
#     doctor_image = doctor.get('photo', None)
#     specialties = doctor['specialties']
#     address = doctor['address']
#     phone = doctor['phone_number']

#     if request.method == "GET":
#         return render_template("scheduling.html", doctor_image=doctor_image,
#                                doctor_name=doctor_name, doctor_specialty=specialties,
#                                doctor_address=address, doctor_phone=phone, medical_plans=medical_plans)

#     elif request.method == "POST":
#         day = str(request.form.get('day'))
#         time_slot = request.form.get('time')
#         patient_id = session.get('_id', None)

#         if not patient_id:
#             flash('You need to be logged in to schedule an appointment.', 'danger')
#             return redirect(url_for('signinGET'))

#         # Convert the day and time_slot into epoch timestamp
#         appointment_time = time.mktime(time.strptime(day + " " + time_slot, '%m-%d-%Y %H:%M%p'))

#         # Here, check if the slot is already booked.
#         existing_appointment = mongo.db.appointments.find_one({"timestamp": appointment_time, "doctor_id": ObjectId(doc_id)})
#         if existing_appointment:
#             flash('The slot is already booked. Please choose another slot.', 'danger')
#             return redirect(url_for('schedule', doc_id=doc_id))

#         # Otherwise, create the appointment.
#         appointment = {
#             "doctor_id": ObjectId(doc_id),
#             "patient_id": ObjectId(patient_id),
#             "timestamp": appointment_time
#         }

#         mongo.db.appointments.insert_one(appointment)
#         flash('Appointment scheduled successfully!', 'success')
#         return redirect(url_for('profile'))