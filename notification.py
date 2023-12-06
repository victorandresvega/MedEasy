import locale
from datetime import datetime
from bson import ObjectId

# Set the locale to Spanish
locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
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
        appt_time_string = appt_time.strftime("%d de %B de %Y %I:%M:%S %p")
        #With all the data that is retrieved, now we create an appropriate message for the notification based 
        #on the type of notification received
        match type:
            case 'Appointment Created':
                message = "Cita nueva creada por {0}.".format(sender_name)
            case 'Appointment Deleted by Patient':
                message = "Cita cancelada por {0}.".format( sender_name)
            case 'Appointment Modified by Patient':
                message = "Cita modificada por {0}.".format(sender_name)
            case 'Twenty four hours till appointment':
                message = "Recordatorio de su cita con {0}.".format(sender_name)
        notification = Notification(ObjectId(recipient_id), ObjectId(sender_id), sender_name, sender_phone_number, type, appt_time_string, message)
        notification_document = notification.to_json()
        collection.insert_one(notification_document)
        return notification_document


        