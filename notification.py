from datetime import datetime
from bson import ObjectId

class Notification:
    def __init__(self, recipient_id, sender_id, sender_name, sender_phone_number, type, appointment_time, message):
        self.recipient_id = recipient_id
        self.sender_id = sender_id
        self.sender_name = sender_name
        self.sender_phone_number = sender_phone_number
        self.type = type
        self.appointment_time = appointment_time
        self.message = message

    def to_json(self):
        return {
            'recipient_id' : self.recipient_id,
            'sender_id' : self.sender_id,
            'sender_name' : self.sender_name,
            'sender_phone_number' : self.sender_phone_number,
            'type' : self.type,
            'appointment_time' : self.appointment_time,
            'message' : self.message

        }

    @staticmethod
    def createNotification(recipient_id, sender_id, type, appointment_time, database):
        collection = database.notifications
        #Retrieve sender data from the database
        sender_data = database.users.find_one({"_id": ObjectId(sender_id)})
        sender_name = sender_data["payload"]["first_name"] + " " + sender_data["payload"]["last_name"]
        sender_phone_number = sender_data["payload"]["phone_number"]
        appt_time = datetime.fromtimestamp(appointment_time)
        #With all the data that is retrieved, now we create an appropriate message for the notification based 
        #on the type of notification received
        match type:
            case 'Appointment Created':
                message = "Cita nueva creada por {0} a este tiempo: {1}. El numero de telefono del paciente es {2}.".format(sender_name, appt_time, sender_phone_number)
            case 'Appointment Deleted by Patient':
                message = "Cita programada para {0} borrada por {1}. El numero de telefono del paciente es {2}.".format(appt_time, sender_name, sender_phone_number)
            case 'Appointment Modified by Patient':
                message = "Cita modificada por {0}. El nuevo tiempo de la cita es {1}. El numero de telefono del paciente es {2}".format(sender_name, appt_time, sender_phone_number)
            case 'Twenty four hours till appointment':
                message = "Esto es un recordatorio que usted tiene una cita con {0} a este tiempo: {1}.".format(sender_name, appt_time)
        notification = Notification(ObjectId(recipient_id), ObjectId(sender_id), sender_name, sender_phone_number, type, appointment_time, message)
        notification_document = notification.to_json()
        collection.insert_one(notification_document)
        return notification_document


        