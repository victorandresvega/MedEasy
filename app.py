import os
import certifi
import time

from flask import Flask, render_template, request, redirect, flash, session, url_for, jsonify
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
    user_role = session.get('user_role', None)
    return render_template('home.html', users=users, specialties=specialties, logged_in=logged_in, user_role=user_role)


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

        # Convert clock_in and clock_out values to HH:MM format
        schedule["clock_in"] = convert_to_24h(request.form.get('clock_in'))
        schedule["clock_out"] = convert_to_24h(request.form.get('clock_out'))

        
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

def convert_to_24h(time_str):
    """ Convert time from 12 hour format (with AM/PM) to 24 hour format """
    try:
        time_obj = datetime.strptime(time_str, '%I:%M %p')
        return time_obj.strftime('%H:%M')
    except:
        return time_str


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
        appointment_date = datetime.fromtimestamp(appointment['timestamp']).strftime('%m-%d-%Y')
        appointment_time = time_filter(appointment['timestamp'])

        appointment['date'] = appointment_date
        appointment['time'] = appointment_time



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
            user.payload['schedule'] = {"work_days": [], "clock_in": "00:00", "clock_out": "00:00"}

        # Get clock_in and clock_out values directly from the payload
        clock_in_time = convert_to_am_pm(user.payload['schedule'].get('clock_in', '00:00'))
        clock_out_time = convert_to_am_pm(user.payload['schedule'].get('clock_out', '00:00'))

        return render_template('doctor.html', doctor_email=user, doctor=user.payload, photo=photo_data, clock_in_time=clock_in_time, clock_out_time=clock_out_time)



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

def convert_to_am_pm(time_str):
    """ Convert time from 24-hour format to 12 hour format with AM/PM """
    try:
        time_obj = datetime.strptime(time_str, '%H:%M')
        return time_obj.strftime('%I:%M %p')
    except Exception as e:
        return time_str  # Return the original string if there's an error in conversion

def convert_to_24h(time_str):
    """ Convert time from 12 hour format (with AM/PM) to 24 hour format """
    try:
        time_obj = datetime.strptime(time_str, '%I:%M %p')
        return time_obj.strftime('%H:%M')
    except:
        return time_str


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
        
        # Check if scheduling values are missing and set them to default values
        if 'schedule' not in user.payload:
            user.payload['schedule'] = {
                "work_days": [],           # Default: empty list for work days
                "clock_in": "09:00",       # Default clock in: 9:00 AM
                "clock_out": "17:00"       # Default clock out: 5:00 PM
            }
        
        if request.method == 'POST':
            email = request.form.get('email', user.email)
            first_name = helper_getVal('first_name', request.form, user.payload)
            last_name = helper_getVal('last_name', request.form, user.payload)
            address = helper_getVal('address', request.form, user.payload)
            phone_number = helper_getVal('phone_number', request.form, user.payload)
            specialties = helper_getValList('specialties[]', request.form, user.payload)
            medical_coverages = helper_getValList('medical_coverages[]', request.form, user.payload)
            
            # Get clock_in and clock_out values directly from the payload
            clock_in_time = convert_to_24h(request.form.get('clock_in'))
            clock_out_time = convert_to_24h(request.form.get('clock_out'))

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
            # Convert clock_in and clock_out values to HH:MM format
            clock_in_time = convert_to_24h(request.form.get('clock_in', user.payload.get('schedule', {}).get('clock_in', '00:00')))
            clock_out_time = convert_to_24h(request.form.get('clock_out', user.payload.get('schedule', {}).get('clock_out', '00:00')))


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

def epoch_to_human_readable(epoch_time):
    return datetime.fromtimestamp(epoch_time).strftime('%I:%M %p')

@app.template_filter('time')
def time_filter(s, format='%H:%M'):
    if s is None:
        return 'N/A'
    try:
        time_obj = datetime.strptime(s, '%H:%M')
        return time_obj.strftime(format)
    except Exception as e:
        return s  # Return the original string if there's an error in conversion

def convert_to_24h(time_str):
    """ Convert time from 12 hour format (with AM/PM) to 24 hour format """
    try:
        time_obj = datetime.strptime(time_str, '%I:%M %p')
        return time_obj.strftime('%H:%M')
    except:
        return time_str


@app.route("/schedule/<doc_id>", methods=["GET", "POST"])
def schedule(doc_id):
    user = mongo.db.users.find_one({"_id": ObjectId(doc_id)})
    if not user:
        flash('Doctor not found.', 'danger')
        return redirect(url_for('home'))

    doctor_data = user['payload']
    doctor_instance = Doctor(
        doctor_data['first_name'],
        doctor_data['last_name'],
        doctor_data['specialties'],
        doctor_data['address'],
        doctor_data['medical_coverages'],
        doctor_data['phone_number'],
        doctor_data.get('photo'),
        doctor_data.get('schedule')
    )

    time_slots = doctor_instance.get_time_slots()

    if request.method == "GET":
        clock_in_AmPm = convert_to_am_pm(doctor_data.get('schedule', {}).get('clock_in', '00:00'))
        clock_out_AmPm = convert_to_am_pm(doctor_data.get('schedule', {}).get('clock_out', '00:00'))
        clock_in_24 = convert_to_24h(doctor_data.get('schedule', {}).get('clock_in', '00:00'))
        clock_out_24 = convert_to_24h(doctor_data.get('schedule', {}).get('clock_out', '00:00'))
        work_days = [Doctor.day_to_fullcalendar_format(day) for day in  user['payload']['schedule'].get('work_days', [])]
        
        
        return render_template("scheduling.html", doctor=doctor_data, time_slots=time_slots, clock_in_AmPm=clock_in_AmPm, clock_out_AmPm=clock_out_AmPm, clock_in_24=clock_in_24, clock_out_24=clock_out_24, work_days=work_days, doc_id=doc_id )

    elif request.method == "POST":
        selectedEpoch = request.json['selectedEpoch']
        patient_id = session.get('_id', None)

        if not patient_id:
            return jsonify({"success": False, "message": "You need to be logged in to schedule an appointment."})

        # Check if the slot is already booked.
        existing_appointment = mongo.db.appointments.find_one({"timestamp": selectedEpoch, "doctor_id": ObjectId(doc_id)})
        if existing_appointment:
            return jsonify({"success": False, "message": "The slot is already booked. Please choose another slot."})

        # Otherwise, create the appointment.
        appointment = {
            "doctor_id": ObjectId(doc_id),
            "patient_id": ObjectId(patient_id),
            "timestamp": selectedEpoch
        }

        mongo.db.appointments.insert_one(appointment)
        return jsonify({"success": True, "message": "Appointment scheduled successfully!"})  

        
    time_slots = get_timeslots_for_fullcalendar(Doctor)
    # Get the current date
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    # Check the already booked slots for the doctor from today onwards
    booked_appointments = mongo.db.appointments.find({"doctor_id": ObjectId(doc_id), "timestamp": {"$gt": current_date}})
    booked_times = [{"title": "Booked", "start": datetime.fromtimestamp(appointment["timestamp"]).isoformat(), "color": "red"} for appointment in booked_appointments]

    return jsonify(time_slots + booked_times)



def get_timeslots_for_fullcalendar(doctor_obj):
    time_slots = doctor_obj.get_time_slots()
    formatted_slots = []
    
    for slot in time_slots:
        start_time = datetime.strptime(slot["start"], "%H:%M").isoformat() # Using 24-hour format
        end_time = datetime.strptime(slot["end"], "%H:%M").isoformat()  # Using 24-hour format

        formatted_slots.append({
            "title": "Available",
            "start": slot["day"] + "T" + start_time,
            "end": slot["day"] + "T" + end_time,
            "color": "green"
        })

    return formatted_slots

@app.route('/schedule_events/<doc_id>', methods=['GET'])
def schedule_events(doc_id):
    doctor_data = mongo.db.users.find_one({"_id": ObjectId(doc_id), "role": "doctor"})
    
    if not doctor_data:
        return jsonify({"error": "Doctor not found!"}), 404

    doctor_obj = Doctor(
        doctor_data['payload']['first_name'],
        doctor_data['payload']['last_name'],
        doctor_data['payload']['specialties'],
        doctor_data['payload']['address'],
        doctor_data['payload']['medical_coverages'],
        doctor_data['payload']['phone_number'],
        doctor_data['payload'].get('photo'),
        doctor_data['payload'].get('schedule')
    )

    time_slots = get_timeslots_for_fullcalendar(doctor_obj)
    
    time_slots = get_timeslots_for_fullcalendar(Doctor)

    # Get the current date
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    # Check the already booked slots for the doctor from today onwards
    booked_appointments = mongo.db.appointments.find({"doctor_id": ObjectId(doc_id), "timestamp": {"$gt": current_date}})
    booked_times = [{"title": "Booked", "start": datetime.fromtimestamp(appointment["timestamp"]).isoformat(), "color": "red"} for appointment in booked_appointments]

    return jsonify(time_slots + booked_times)
