from datetime import datetime

class Appointment:
    def __init__(self, _id, doctor_id, patient_id, timestamp):
        self._id = _id
        self.doctor_id = doctor_id
        self.patient_id = patient_id
        self.timestamp = timestamp

    @classmethod
    def get_data(cls, data):
        return cls(
            _id=data.get('_id', None),
            doctor_id=data.get('doctor_id', None),
            patient_id=data.get('patient_id', None),
            timestamp=data.get('timestamp', None)
        )

    def set_data(self):
        return {
            "_id": self._id,
            "doctor_id": self.doctor_id,
            "patient_id": self.patient_id,
            "timestamp": self.timestamp
        }

    def save_to_db(self, db):
        db.appointments.insert_one(self.set_data())
        
    # Convert epoch to date
    @staticmethod
    def epoch_to_date(epoch):
        return datetime.fromtimestamp(int(epoch)).strftime('%m/%d/%Y')  # MM/DD/YYYY format

    # Convert epoch to time
    @staticmethod
    def epoch_to_time(epoch):
        return datetime.fromtimestamp(int(epoch)).strftime('%I:%M %p')  #AM/PM format
