import re
from datetime import datetime, timedelta

class Doctor:
    medicalSpecialties = sorted({
        'Cardiólogo', 'Dermatólogo', 'Alergista', 'Generalista',
        'Pediatra', 'Ortopeda', 'Oftalmólogo', 'Radiólogo'
    })

    medicalCoverages = sorted({
        'Triple-S Salud', 'Molina Healthcare of Puerto Rico',
        'MMM (Medicare y Mucho Más)', 'PMC Medicare Choice','Humana'
    })
    
    daysWeek = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

    def __init__(self, first_name, last_name, specialties, address, medical_coverages, phone_number, photo, schedule=None):
        self.first_name = self.valid_first_name(first_name)
        self.last_name = self.valid_last_name(last_name)
        self.address = self.valid_address(address)
        self.phone_number = self.valid_phone_number(phone_number)
        self.photo = self.valid_photo(photo)
        self.specialties = specialties
        self.medical_coverages = medical_coverages
        self.role = 'doctor'
        self.schedule = schedule or {"work_days": [], "clock_in": "00:00", "clock_out": "00:00"}

    def to_json(self):
        return {
            'first_name': self.first_name,
            'last_name': self.last_name,
            'address': self.address,
            'specialties': self.specialties,
            'medical_coverages': self.medical_coverages,
            'phone_number': self.phone_number,
            'doc_id': self.doc_id,
            'photo': self.photo,
            'role': self.role,
            'schedule': self.schedule
        }

# TODO REVIEW
    @staticmethod
    def create_doctor(first_name, last_name, specialties, address, lat, lng, medical_coverages, phone_number, database):
        doctor = Doctor(first_name, last_name, specialties, address, lat, lng, medical_coverages, phone_number)
        doctor_document = doctor.to_json()
        collection = database.doctors
        collection.insert_one(doctor_document)
        return doctor

    @staticmethod
    def get_doctors(mongo):
        return mongo.doctors.find()

    @staticmethod
    def get_filtered_doctors(database, specialty, name):
        collection = database.users
        #Regex expression to ignore case in inputted name
        regex_case_ignore = {"$regex": f".*{re.escape(name)}.*","$options": "i"}
        #Pipeline to be used in the aggregate functions below. Basically looks to see if the input name matches 
        #the first or last names of the doctors in the collection
        pipeline = [{"$match":{"$or":[{"payload.first_name":regex_case_ignore},{"payload.last_name":regex_case_ignore}]}}]
        if specialty == "" and name == "":
            return collection.find()
        elif specialty == "":
            #This function basically queries both the first_name and last_name fields inside the payload
            return collection.aggregate(pipeline)
        elif name == "":
            return collection.find({'payload.specialties': specialty})
        name_filter = collection.aggregate(pipeline)
        result = []
        #Goes through all the matches that were found with the name query, verifies if they are doctors first (otherwise an error occurs when trying to access the specialties)
        for doctor in name_filter:
            if doctor['role'] == 'doctor':
                for spty in doctor['payload']['specialties']:
                    if spty == specialty:
                        result.append(doctor)
        return result
    
    def get_time_slots(self):
        slots = []
        clock_in = datetime.strptime(self.schedule["clock_in"], '%H:%M')
        clock_out = datetime.strptime(self.schedule["clock_out"], '%H:%M')
        
        while clock_in <= clock_out:
            slots.append(clock_in.strftime('%H:%M'))
            clock_in += timedelta(minutes=30)
        
        return slots
    
    def day_to_fullcalendar_format(day):
        mapping = {
            'Domingo': 0,
            'Lunes': 1,
            'Martes': 2,
            'Miércoles': 3,
            'Jueves': 4,
            'Viernes': 5,
            'Sábado': 6,
        }
        return mapping.get(day, -1)




    # --------------------------------------------------------------------------

    # TODO review all validations
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

    def valid_phone_number(self, phone_number):
        pattern = re.compile(
            r"^(?:\+?1[-.\s]?)?(\()?(\d{3})(?(1)\))[-.\s]?(\d{3})[-.\s]?(\d{4})$")
        if not pattern.match(phone_number):
            raise ValueError("Invalid doctor phone number format")
        return phone_number
    
    # TODO Review and Modify for better validation method
    def valid_photo(self, photo):
        if type(photo) != str:
            return '/static/img/generic-user-pfp.png'

        pattern = re.compile(r'https://[a-zA-Z0-9-]+\.[a-zA-Z0-9/.]+[.](jpg|jpeg|png|gif)$')
            
        if not pattern.match(photo):
            return '/static/img/generic-user-pfp.png'
        return photo
    
    # -------------------------------------------------------------------------
    
    
    # TODO REVIEW
    @staticmethod
    def get_doctor_by_id(doc_id, mongo):
        user = mongo.db.users.find_one({"user_id": "_id", "role": "doctor"})
        if user:
            doctor_data = user["payload"]
            return Doctor(
                doctor_data['first_name'],
                doctor_data['last_name'],
                doctor_data['specialties'],
                doctor_data['address'],
                doctor_data.get('lat'),
                doctor_data.get('lng'),
                doctor_data['medical_coverages'],
                doctor_data['phone_number'],
                doctor_data.get('photo', '/static/img/generic-user-pfp.png')
            )
        return None
    
    @staticmethod
    def get_doctor_by_email(email, mongo):
        user = mongo.db.users.find_one({"email": email, "role": "doctor"})
        if user:
            doctor_data = user["payload"]
            return Doctor(doctor_data['first_name'], doctor_data['last_name'], doctor_data['phone_number'])
        return None
