import sqlite3
import cv2
from pyzbar.pyzbar import decode
from flask import Flask, render_template, Response, jsonify
import threading
import time

# Initialize Flask app
app = Flask(__name__)

# Database file location
DB_PATH = 'C:\\Users\\iamak\\barcodes.db'

# Global variables to control the webcam and frame
webcam_active = False
frame = None
barcode_result = None
frame_processed = False
barcode_detected = False
barcode_decoded = False
id_validated = False

# Lock for thread safety
frame_lock = threading.Lock()

# Function to fetch data from the database
def fetch_student_data(barcode_data):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM student WHERE roll_no = ?", (barcode_data,))
    data = cursor.fetchone()
    conn.close()
    return data

# Webcam capturing function
def start_webcam():
    global webcam_active, frame, barcode_result, frame_processed, barcode_detected, barcode_decoded, id_validated
    cap = cv2.VideoCapture(0)  # Use camera index 0 (or change if needed)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)  # Set frame width
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)  # Set frame height

    if not cap.isOpened():
        print("Error: Could not open the webcam.")
        return
    
    while webcam_active:
        ret, img = cap.read()
        frame_processed = False
        barcode_detected = False
        barcode_decoded = False
        id_validated = False

        if ret:
            frame_processed = True  # Frame has been captured
            # Convert to grayscale for better barcode detection
            gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Decode the barcode from the grayscale frame
            barcodes = decode(gray_img)
            if barcodes:
                barcode_detected = True  # Barcode detected
                for barcode in barcodes:
                    barcode_data = barcode.data.decode('utf-8')
                    print(f"Barcode detected: {barcode_data}")
                    barcode_decoded = True  # Barcode decoded
                    student_data = fetch_student_data(barcode_data)
                    if student_data:
                        barcode_result = f"Name: {student_data[1]}, Roll No: {student_data[0]}, Department: {student_data[2]}, Academic Year: {student_data[3]}"
                        id_validated = True  # Valid ID card
                    else:
                        barcode_result = "Invalid ID card data not found."
                        id_validated = False
            else:
                barcode_result = "No barcode detected."
                print("No barcode detected in this frame.")
                
            with frame_lock:
                frame = img.copy()  # Copy the frame for streaming
        else:
            print("Error: Failed to capture frame.")
            break
    cap.release()

# Route to the main page
@app.route('/')
def index():
    return render_template('index.html')
    # return "Hello World"

# Route to start the webcam
@app.route('/start')
def start():
    global webcam_active, barcode_result
    if not webcam_active:
        webcam_active = True
        barcode_result = None  # Reset the barcode result
        threading.Thread(target=start_webcam).start()
    return jsonify({"status": "started"})

# Route to stop the webcam
@app.route('/stop')
def stop():
    global webcam_active
    webcam_active = False
    return jsonify({"status": "stopped"})

# Route to stream video frames
@app.route('/video_feed')
def video_feed():
    global frame
    def generate():
        while webcam_active:
            with frame_lock:
                if frame is None:
                    continue
                # Encode frame as JPEG
                _, buffer = cv2.imencode('.jpg', frame)
                frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

# Route to get the processing status
@app.route('/processing_status')
def processing_status():
    global frame_processed, barcode_detected, barcode_decoded, id_validated
    return jsonify({
        "frame_processed": frame_processed,
        "barcode_detected": barcode_detected,
        "barcode_decoded": barcode_decoded,
        "id_validated": id_validated
    })

# Route to get the barcode result
@app.route('/barcode_result')
def barcode_result_route():
    global barcode_result
    if barcode_result:
        return jsonify({"result": barcode_result})
    else:
        return jsonify({"status": "Waiting for barcode scan..."})

if __name__ == '__main__':
    app.run(debug=True)
