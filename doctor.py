import hashlib
import time
import re


class Doctor:

    medicalSpecialties = sorted({'Cardiólogo', 'Dermatólogo', 'Alergista', 'Generalista', 'Pediatra', 'Ortopeda', 'Oftalmólogo', 'Radiólogo', 'Gastroenterologo'})
    
    curr_specialties = {'cardiologist', 'dermatologist',
                        'allergist', 'generalist', 'pediatrician', 'orthopedist', 'ophtalmologist', 'radiologist'}

    def __init__(self, first_name, last_name, specialties, address, lat, lng, medical_coverages, phone_number):
        self.first_name = self.valid_first_name(first_name)
        self.last_name = self.valid_last_name(last_name)
        self.specialties = self.valid_specialties(specialties)
        self.address = self.valid_address(address)
        self.lat = self.valid_lat(lat)
        self.lng = self.valid_lng(lng)
        self.medical_coverages = self.valid_medical_coverages(
            medical_coverages)
        self.phone_number = self.valid_phone_number(phone_number)
        self.doc_id = self.generate_doctor_id()
        self.role = 'doctor'

    def to_json(self):
        return {
            'first_name': self.first_name,
            'last_name': self.last_name,
            'specialties': self.specialties,
            'address': self.address,
            'lat': self.lat,
            'lng': self.lng,
            'medical_coverages': self.medical_coverages,
            'phone_number': self.phone_number,
            'doc_id': self.doc_id,
            'role': self.role
        }

# TODO REMOVE 
    @staticmethod
    def create_doctor(first_name, last_name, specialties, address, lat, lng, medical_coverages, phone_number, database):
        doctor = Doctor(first_name, last_name, specialties, address,
                        lat, lng, medical_coverages, phone_number)
        doctor_document = doctor.to_json()
        collection = database.doctors
        collection.insert_one(doctor_document)
        return doctor

    @staticmethod
    def get_doctors(mongo):
        return mongo.doctors.find()
    
    #Helper function for searching for names to be used in get_filtered_doctors() below
    @staticmethod
    def find_names_helper(database, search_names):
        doctors = database.users.find({"role":"doctor"})
        result = []
        for doctor in doctors:
            first_name = doctor["payload"]["first_name"]
            last_name = doctor["payload"]["last_name"]
            if any(name.lower() in first_name.lower() or name.lower() in last_name.lower() for name in search_names):
                result.append(doctor)
        return result

    @staticmethod
    def get_filtered_doctors(database, specialty, name):
        collection = database.users
        search_names = name.split()
        #Regex expression to ignore case in inputted name
        #regex_case_ignore = {"$regex": f".*{re.escape(name)}.*","$options": "i"}
        #Pipeline to be used in the aggregate functions below. Basically looks to see if the input name matches 
        #the first or last names of the doctors in the collection
        #pipeline = [{"$match":{"$or":[{"payload.first_name":regex_case_ignore},{"payload.last_name":regex_case_ignore}]}}]
        if specialty == "" and name == "":
            return collection.find({"role":"doctor"})
        elif specialty == "":
            #This function basically queries both the first_name and last_name fields inside the payload
            result = Doctor.find_names_helper(database, search_names)
            return result
        elif name == "":
            return collection.find({'payload.specialties': specialty})
        name_filter = Doctor.find_names_helper(database, search_names)
        result = []
        #Goes through all the matches that were found with the name query, verifies if they are doctors first (otherwise an error occurs when trying to access the specialties)
        for doctor in name_filter:
            if doctor['role'] == 'doctor':
                for spty in doctor['payload']['specialties']:
                    if spty == specialty:
                        result.append(doctor)
        return result
    

    def valid_first_name(self, first_name):
        pattern = re.compile(r"^[A-Z][a-z'-]{1,24}$")
        if not pattern.match(first_name):
            raise ValueError("Invalid doctor first name format")
        return first_name

    def valid_last_name(self, last_name):
        pattern = re.compile(r"^[A-Z][a-z'-]{1,24}$")
        if not pattern.match(last_name):
            raise ValueError("Invalid doctor last name format")
        return last_name

    def valid_specialties(self, specialties):
        if type(specialties) != list:
            raise TypeError("The doctor's specialties is not of type list")
        for specialty in specialties:
            if type(specialty) != str:
                raise TypeError("The doctor's specialty is not of type string")
            if specialty not in Doctor.curr_specialties:
                raise ValueError(f"{specialty} is not a valid specialty.")
        return specialties

    def valid_address(self, address):
        if type(address) != str:
            raise TypeError("The doctor's address is not of type str")
        return address

    def valid_lat(self, lat):
        if type(lat) != float:
            raise TypeError("The the doctor's office latitude cordinate is not of type float")
        if lat <= -91.0 or lat >= 90.0:
            raise ValueError("The Doctor's office latitude cordinate is not in range of [-90 to 90].")
        return lat
            
    def valid_lng(self, lng):
        if type(lng) != float:
            raise TypeError("The the doctor's office latitude cordinate is not of type float")
        if lng <= -181.0 or lng >= 181.0:
            raise ValueError("The Doctor's office latitude cordinate is not in range of [-180 to 180].")
        return lng
    
    def valid_medical_coverages(self, medical_coverages):
        if type(medical_coverages) != list:
            raise TypeError("Medical coverages should be of type list")
        
        for coverage in medical_coverages:
            if type(coverage) != str:
                raise TypeError("Medical coverage should be of type str")
    
        return medical_coverages

    def valid_phone_number(self, phone_number):
        pattern = re.compile(
            r"^(?:\+?1[-.\s]?)?(\()?(\d{3})(?(1)\))[-.\s]?(\d{3})[-.\s]?(\d{4})$")
        if not pattern.match(phone_number):
            raise ValueError("Invalid doctor phone number format")
        return phone_number

    # TODO REMOVE
    def generate_doctor_id(self):
        cur_time = str(time.time())
        hashed_time = hashlib.sha1()
        hashed_time.update(cur_time.encode("utf8"))
        return hashed_time.hexdigest()
    
    # TODO Check use
    @staticmethod
    def get_doctor_by_id(doc_id, mongo):
        user = mongo.db.users.find_one({"user_id": doc_id, "role": "doctor"})
        if user:
            doctor_data = user["payload"]
            return Doctor(
                doctor_data['first_name'],
                doctor_data['last_name'],
                doctor_data['specialties'],
                doctor_data['address'],
                doctor_data.get('lat', 0.0),
                doctor_data.get('lng', 0.0),
                doctor_data['medical_coverages'],
                doctor_data['phone_number'],
                doctor_data.get('photo_url', '/AppointMED/static/images/generic-user-pfp.png')
            )
        return None
    
    @staticmethod
    def get_doctor_by_email(email, mongo):
        user = mongo.db.users.find_one({"email": email, "role": "doctor"})
        if user:
            doctor_data = user["payload"]
            return Doctor(doctor_data['first_name'], doctor_data['last_name'], doctor_data['phone_number'])
        return None
