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
from datetime import datetime, timedelta
import requests
from flask_apscheduler import APScheduler
from apscheduler.triggers.cron import CronTrigger



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

# Create the scheduler instance
scheduler = APScheduler()

# Start the scheduler
scheduler.start()

# Function to cancel overdue appointments
def cancel_overdue_appointments():
    current_time = datetime.now()
    one_hour_in_future = current_time + timedelta(hours=1)
    one_hour_in_future_epoch = one_hour_in_future.timestamp()

    appointments_to_cancel = mongo.db.appointments.find({"timestamp": {"$lt": one_hour_in_future_epoch}})

    for appointment in appointments_to_cancel:
        mongo.db.appointments.delete_one({"_id": appointment["_id"]})

# Schedule the job to run every hour
scheduler.add_job(func=cancel_overdue_appointments, trigger=CronTrigger.from_crontab('0 * * * *'), id='cancel_overdue_appointments')

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
    doctor = mongo.db.users.find({"role": "doctor"})
    coordinates = Doctor.get_doctor_coordinates(doctor)
    print(coordinates)
    logged_in = "_id" in session
    user_role = session.get('user_role', None)
    return render_template('home.html', users=users, specialties=specialties, logged_in=logged_in, user_role=user_role, coordinates=coordinates)


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

        flash('Su sesión ha inicida exitosamente!', 'success')
        return redirect(url_for('home'))
    else:
        flash("Inicio de sesión fallido. Verifique el correo electrónico y la contraseña.", 'danger')
    return signinGET()


@app.route('/signup', methods=['GET'])
def signupGET():
    specialties = Doctor.medicalSpecialties
    medical_coverages = Doctor.medicalCoverages
    work_days = Doctor.daysWeek
    municipalities = Doctor.municipalities
    
    return render_template('signup.html', specialties=specialties, medical_coverages=medical_coverages, work_days= work_days, municipalities=municipalities)
    
@app.route('/signup', methods=['POST'])
def signupPOST():
    account_type = request.form.get('accountType')
    email = request.form.get('email')
    # Check if the email already exists in the database
    existing_user = mongo.db["users"].find_one({"email": email})
    if existing_user:
        flash('Ya existe una cuenta con ese correo electrónico', 'danger')
        return signupGET()

    # Continue with the rest of the signup process if email is unique
    password = request.form.get('password')
    payload = {}

    # Fields specific to the patient role
    if account_type == "patient":
        payload["first_name"] = request.form.get('patient_first_name')
        payload["last_name"] = request.form.get('patient_last_name')
        payload["phone_number"] = request.form.get('patient_phone_number')

    # Fields specific to the doctor role
    if account_type == "doctor":
        payload["first_name"] = request.form.get('first_name')
        payload["last_name"] = request.form.get('last_name')

        # Concatenate the address line 1, pueblo (municipality), and zip code
        address_line1 = request.form.get('address1')
        pueblo = request.form.get('pueblo')
        zip_code = request.form.get('zip_code')
        full_address = f"{address_line1}, {pueblo}, Puerto Rico {zip_code}"
        

        payload["address"] = full_address
        payload["specialties"] = request.form.getlist('specialties[]')
        payload["medical_coverages"] = request.form.getlist('medical_coverages[]')
        payload["phone_number"] = request.form.get('phone_number')

        schedule = {}
        schedule["work_days"] = request.form.getlist('work_days[]')

        # Convert clock_in and clock_out values to HH:MM format
        schedule["clock_in"] = convert_to_24h(request.form.get('clock_in'))
        schedule["clock_out"] = convert_to_24h(request.form.get('clock_out'))

        payload["schedule"] = schedule  # Add schedule to the payload

        coordinates = {}
        #Convert address string to coordinate values for use in the Map and return as a
        #dictionary with keys "latitude" and "longitude"
        coordinates = nominatim_geocoding(full_address)
        
        payload["coordinates"] = coordinates #add coordinates to payload

        photo_file = request.files.get('photo')
        if photo_file and photo_file.filename != '':
            photo_path = os.path.join("static/img/", photo_file.filename)
            photo_file.save(photo_path)
            encoded_photo = Photo.encodeImage(photo_path)
            os.remove(photo_path)
        else:
            encoded_photo = Photo.encodeImage("https://freesvg.org/img/abstract-user-flat-4.png")  # Default image

        payload["photo"] = encoded_photo

    # Create the user with the above payload
    created_user = User.create_user(
        bcrypt, email=email, password=password, role=account_type, payload=payload, database=mongo.db)

    session['_id'] = created_user._id
    session['user_role'] = account_type
    flash('Cuenta creada exitosamente', 'success')
    return redirect(url_for('home'))

def convert_to_24h(time_str):
    """Convert time from 12-hour format (with AM/PM) to 24-hour format"""
    try:
        time_obj = datetime.strptime(time_str, '%I:%M %p')
        return time_obj.strftime('%H:%M')
    except:
        return time_str
    
#Function that accepts a string address and returns a dictionary containing the coordinates of the address,
#to be used when a doctor first signs up to the site or when they modify their address information
def nominatim_geocoding(address):
    #Coordinates point to Null Island as the default value
    coordinates = {
        "latitude" : 0,
        "longitude" : 0
    }
    #This function makes an HTTP request to the OpenStreetMap Nominatim to geocode the address of a doctor
    #and return the coordinates 
    endpoint = "https://nominatim.openstreetmap.org/search"

    parameters = {"q": address, "format": "json"}

    response = requests.get(endpoint, params=parameters)

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the JSON response
        data = response.json()

        if data:
            # Extract the latitude and longitude from the response
            lat = float(data[0]['lat'])
            lon = float(data[0]['lon'])

            coordinates["latitude"] = lat
            coordinates["longitude"] = lon
        else:
            flash("Error")
    else:
        flash("Error: Unable to connect to Nominatim API.")
    return coordinates




@app.route('/signout')
def signout():
    session.clear()
    flash('Su sesión ha cerrado exitosamente', 'success')
    return redirect(url_for('home'))


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    user_id = session.get('_id', None)
    user = User.get_user_by_id(user_id, mongo.db)
    user_appointments = list(mongo.db.appointments.find({"patient_id": ObjectId(user_id)}))


    if not user:  
        flash('Usuario no encontrado', 'danger')
        return redirect(url_for('home'))

    # Convert the epoch timestamp to date and time for each appointment
    for appointment in user_appointments:
        appointment_date = datetime.fromtimestamp(appointment['timestamp']).strftime('%m-%d-%Y')
        appointment_time = time_filter(appointment['timestamp'])

        appointment['date'] = appointment_date
        appointment['time'] = convert_to_am_pm(appointment_time)

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

        return render_template('doctor.html', doctor_email=user, doctor=user.payload, photo=photo_data, clock_in_time=clock_in_time, clock_out_time=clock_out_time, doc_id=user_id)



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
        flash('Tipo de perfil inválido', 'danger')
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
    municipalities = Doctor.municipalities
    specialties = Doctor.medicalSpecialties
    medical_coverages = Doctor.medicalCoverages
    work_days = Doctor.daysWeek
    phys_address = ""
    pueblo = ""
    zip_code = ""

    if not user:
        flash('Usuario no encontrado', 'danger')
        return redirect(url_for('home'))

    if user.role == "doctor":
        splitted_address = ''
        # Check if scheduling values are missing and set them to default values
        if 'schedule' not in user.payload:
            user.payload['schedule'] = {
                "work_days": [],           # Default: empty list for work days
                "clock_in": "09:00",       # Default clock in: 9:00 AM
                "clock_out": "17:00"       # Default clock out: 5:00 PM
            }
        address = user.payload["address"]
        splitted_address = address.split(",")
        phys_address = ','.join(splitted_address[0:-2])
        pueblo = splitted_address[-2]
        zip_code = splitted_address[-1][12:]
        print(phys_address)
        print(zip_code)
        print(pueblo)
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
            full_address = str(request.form.get('address')) + ", " + str(request.form.get('pueblo')) + ", Puerto Rico " + str(request.form.get('zip_code'))
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
            
            #Location coordinates update
            coordinates = nominatim_geocoding(address)
            updated_payload = {
                "email": email,
                "payload.first_name": first_name,
                "payload.last_name": last_name,
                "payload.specialties": specialties,
                "payload.address": full_address,
                "payload.coordinates": coordinates,
                "payload.phone_number": phone_number,
                "payload.medical_coverages": medical_coverages,
                "payload.schedule.work_days": work_days,
                "payload.schedule.clock_in": clock_in_time,
                "payload.schedule.clock_out": clock_out_time,
            }
            collection = mongo.db.users
            # Check if email already exists in the database
            existing_email = collection.find_one({"email": email})
            if existing_email and str(existing_email['_id']) != str(user_id):
                print(existing_phone['_id'], user_id)
                flash("El correo electrónico ya está en uso", "error")  # Flash an error message
                return redirect(request.url)  # Redirect back to the same page
            existing_phone = collection.find_one({"payload.phone_number": phone_number})
            if existing_phone and str(existing_phone['_id']) != str(user_id):
                print(existing_phone['_id'], user_id)
                flash("Número de teléfono ya está en uso", "error")  # Flash an error message
                return redirect(request.url)  # Redirect back to the same page
            collection.update_one({"_id": ObjectId(user_id)}, {
                "$set": updated_payload
            })

            return redirect(url_for('profile'))

        else:
            # Retrieve current values for clock_in and clock_out
            clock_in_time = user.payload.get('schedule', {}).get('clock_in', '09:00')
            clock_out_time = user.payload.get('schedule', {}).get('clock_out', '17:00')
            print(f'phys_address: {phys_address}')
            # Render the form with the current values
            return render_template('editDoctor.html', doctor_email=user, doctor=user.payload,
                                   specialties=specialties, medical_coverages=medical_coverages, work_days=work_days,
                                   clock_in_time=clock_in_time, clock_out_time=clock_out_time, municipalities=municipalities, pueblo=pueblo, phys_address=phys_address, zip_code=zip_code)

    elif user.role == "patient":
        if request.method == 'POST':
            email = request.form.get('email', user.email)
            first_name = helper_getVal('first_name', request.form, user.payload)
            last_name = helper_getVal('last_name', request.form, user.payload)
            phone_number = helper_getVal('phone_number', request.form, user.payload)

            collection = mongo.db.users
            # Check if email already exists in the database
            existing_email = collection.find_one({"email": email})
            if existing_email and str(existing_email['_id']) != str(user_id):
                flash("El correo electrónico ya está en uso.", "error")  # Flash an error message
                return redirect(request.url)  # Redirect back to the same page
            existing_phone = collection.find_one({"payload.phone_number": phone_number})
            if existing_phone and str(existing_phone['_id']) != str(user_id):
                print(existing_phone['_id'] != user_id)
                print(existing_phone['_id'], user_id)
                flash("Número de teléfono ya está en uso","error")  # Flash an error message
                return redirect(request.url)  # Redirect back to the same page
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
        flash('Tipo de perfil incorrecto', 'danger')
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
def time_filter(epoch_time, format='%H:%M'):
    if epoch_time is None:
        return 'N/A'
    try:
        dt_object = datetime.fromtimestamp(epoch_time)
        return dt_object.strftime(format)
    except Exception as e:
        return str(e) 


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
        flash('No se ha encontrado ningun doctor', 'danger')
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

        coordinates = {"latitude" : doctor_data['coordinates']['latitude'], "longitude" : doctor_data['coordinates']['longitude']}
        
        return render_template("scheduling.html", doctor=doctor_data, time_slots=time_slots, clock_in_AmPm=clock_in_AmPm, clock_out_AmPm=clock_out_AmPm, clock_in_24=clock_in_24, clock_out_24=clock_out_24, work_days=work_days, coordinates=coordinates, doc_id=doc_id)

    elif request.method == "POST":
        selectedEpoch = request.json['selectedEpoch']
        patient_id = session.get('_id', None)

        if not patient_id:
            return jsonify({"success": False, "message": "Por favor inicie session."})

        # Check if the slot is already booked.
        existing_appointment = mongo.db.appointments.find_one({"timestamp": selectedEpoch, "doctor_id": ObjectId(doc_id)})
        if existing_appointment:
            return jsonify({"success": False, "message": "Este espacio de cita ya ha sido ocupado. Por favor intente otro espacio."})

        # Otherwise, create the appointment.
        appointment = {
            "doctor_id": ObjectId(doc_id),
            "patient_id": ObjectId(patient_id),
            "timestamp": selectedEpoch
        }

        mongo.db.appointments.insert_one(appointment)
        return jsonify({"success": True, "message": "Su cita ha sido procesada!"})  

        
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
        if "day" not in slot:  # Error handling
            flash(f"Error: 'day' key not found in slot: {slot}")
            continue  # Skip to the next slot

        start_time = datetime.strptime(slot["start"], "%H:%M").isoformat()  # Using 24-hour format
        end_time = datetime.strptime(slot["end"], "%H:%M").isoformat()  # Using 24-hour format

        formatted_slots.append({
            "title": "Available",
            "start": slot.get("day", "DEFAULT_DAY") + "T" + start_time,  # Using .get() method with default value
            "end": slot.get("day", "DEFAULT_DAY") + "T" + end_time,  # Using .get() method with default value
            "color": "green"
        })

    return formatted_slots


@app.route('/schedule_events/<doc_id>', methods=['GET'])
def schedule_events(doc_id):
    # First, let's fetch all the appointments of the doctor.
    appointments = mongo.db.appointments.find({"doctor_id": ObjectId(doc_id)})
    events = []
    current_time = datetime.now()
    
    for appt in appointments:
        start_time = datetime.fromtimestamp(appt["timestamp"])
        if start_time > current_time:
            end_time = start_time + timedelta(minutes=30)
            event = {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "color": "red",  # marking it as unavailable
                "title": "Ocupado"
            }
            events.append(event)

    return jsonify(events)


@app.route('/create_appointment', methods=['POST'])
def create_appointment():
    data = request.json
    selectedEpoch = data['selectedEpoch']
    doc_id = data['doc_id']
    patient_id = session.get('_id', None)

    # Ensure the patient is logged in
    if not patient_id:
        return jsonify({"success": False, "message": "Debe iniciar sesión como paciente para acceder."})

    # Check if the patient already has an active appointment with the same doctor
    existing_appointment = mongo.db.appointments.find_one({
        "doctor_id": ObjectId(doc_id),
        "patient_id": ObjectId(patient_id),
        "timestamp": {"$gt": int(time.time())}
    })

    if existing_appointment:
        # Replace the existing appointment with the new one
        mongo.db.appointments.update_one({"_id": existing_appointment["_id"]}, {
            "$set": {
                "timestamp": selectedEpoch
            }
        })
        return jsonify({"success": True, "message": "Su cita existente ha sido modificada."})
    else:
        # Create a new appointment
        appointment = {
            "doctor_id": ObjectId(doc_id),
            "patient_id": ObjectId(patient_id),
            "timestamp": selectedEpoch
        }

        mongo.db.appointments.insert_one(appointment)
        return jsonify({"success": True, "message": "Su nueva cita ha sido programada exitosamente!"})

@app.route("/check_existing_appointment", methods=["POST"])
def check_existing_appointment():
    data = request.json
    selectedEpoch = data['selectedEpoch']
    doc_id = data['doc_id']
    patient_id = session.get('_id', None)

    if not patient_id:
        return jsonify({"hasExistingAppointment": False})

    existing_appointment = mongo.db.appointments.find_one({
        "doctor_id": ObjectId(doc_id),
        "patient_id": ObjectId(patient_id),
        "timestamp": {"$gt": int(time.time())}
    })

    if existing_appointment:
        doctor = mongo.db.users.find_one({"_id": ObjectId(doc_id)})['payload']
        doctor_full_name = f"{doctor['first_name']} {doctor['last_name']}"

        return jsonify({
            "hasExistingAppointment": True,
            "doctorName": doctor_full_name,
            "existingAppointment": {
                "_id": str(existing_appointment["_id"]),
                "timestamp": datetime.fromtimestamp(existing_appointment["timestamp"]).strftime("%m/%d/%Y %I:%M %p")
            }
        })
    else:
        print("llegue")
        return jsonify({"hasExistingAppointment": False})


@app.route('/modify_appointment', methods=['POST'])
def modify_appointment():
    data = request.json
    appointment_id = data['appointment_id']
    selectedEpoch = data['selectedEpoch']
    patient_id = session.get('_id', None)

    if not patient_id:
        return jsonify({"success": False, "message": "Debe iniciar sesión como paciente para acceder."})

    existing_appointment = mongo.db.appointments.find_one({
        "_id": ObjectId(appointment_id),
        "patient_id": ObjectId(patient_id)
    })

    if not existing_appointment:
        return jsonify({"success": False, "message": "No tiene permiso para modificar esta cita."})

    # Modify the appointment with the new selected time
    mongo.db.appointments.update_one({"_id": ObjectId(appointment_id)}, {
        "$set": {
            "timestamp": selectedEpoch
        }
    })

    return jsonify({"success": True, "message": "Su cita ha sido modificada exitosamente."})


@app.route('/cancel_appointment/<appointment_id>', methods=['POST'])
def cancel_appointment(appointment_id):
    result = mongo.db.appointments.delete_one({"_id": ObjectId(appointment_id)})
    
    if result.deleted_count > 0:
        return jsonify({"success": True, "message": "Cita cancelada exitosamente."})
    else:
        return jsonify({"success": False, "message": "No se pudo cancelar la cita."})