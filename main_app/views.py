import json
import requests
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render, reverse
from django.views.decorators.csrf import csrf_exempt

from .EmailBackend import EmailBackend
from .models import Attendance, Session, Subject

import csv
from .models import Student, StudentResult
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch

def get_grade(score):
    if score >= 75:
        return "A1"
    elif score >= 70:
        return "B2"
    elif score >= 65:
        return "B3"
    elif score >= 60:
        return "C4"
    elif score >= 55:
        return "C5"
    elif score >= 50:
        return "C6"
    elif score >= 45:
        return "D7"
    elif score >= 40:
        return "E8"
    else:
        return "F9"

def export_results_pdf(request):
    student = Student.objects.get(admin=request.user)
    results = StudentResult.objects.filter(student_id=student)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{student.admin.first_name}_results.pdf"'

    p = canvas.Canvas(response, pagesize=letter)
    width, height = letter

    p.setFont("Helvetica-Bold", 16)
    p.drawString(1 * inch, height - 1 * inch, "Academic Results")
    
    p.setFont("Helvetica", 12)
    p.drawString(1 * inch, height - 1.5 * inch, f"Student Name: {student.admin.first_name} {student.admin.last_name}")
    p.drawString(1 * inch, height - 1.7 * inch, f"Email: {student.admin.email}")
    p.line(1 * inch, height - 2 * inch, width - 1 * inch, height - 2 * inch)

    # Table Header
    y_position = height - 2.5 * inch
    p.setFont("Helvetica-Bold", 12)
    p.drawString(1 * inch, y_position, "Subject")
    p.drawString(3.5 * inch, y_position, "Test (40)")
    p.drawString(4.5 * inch, y_position, "Exam (60)")
    p.drawString(5.5 * inch, y_position, "Total (100)")
    p.drawString(6.5 * inch, y_position, "Grade")

    # Table Rows
    p.setFont("Helvetica", 11)
    for result in results:
        y_position -= 0.3 * inch
        total = result.test + result.exam
        grade = get_grade(total)
        p.drawString(1 * inch, y_position, str(result.subject.name))
        p.drawString(3.5 * inch, y_position, str(result.test))
        p.drawString(4.5 * inch, y_position, str(result.exam))
        p.drawString(5.5 * inch, y_position, str(total))
        p.drawString(6.5 * inch, y_position, grade)

        # Add a new page if space runs out
        if y_position < 1 * inch:
            p.showPage()
            y_position = height - 1 * inch
            p.setFont("Helvetica-Bold", 12)
            p.drawString(1 * inch, y_position, "Subject")
            p.drawString(3.5 * inch, y_position, "Test")
            p.drawString(4.5 * inch, y_position, "Exam")
            p.drawString(5.5 * inch, y_position, "Total")
            p.drawString(6.5 * inch, y_position, "Grade")
            p.setFont("Helvetica", 11)

    p.showPage()
    p.save()
    return response

def export_students_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="students.csv"'

    writer = csv.writer(response)
    writer.writerow(['ID', 'Course', 'Session', 'Phone', 'Guardian Name', 'Guardian Phone'])

    for student in Student.objects.all():
        writer.writerow([
            student.id,
            student.course.name if student.course else '',
            student.session.start_year if student.session else '',
            student.phone,
            student.guardian_name,
            student.guardian_phone
        ])

    return response

def login_page(request):
    if request.user.is_authenticated:
        if request.user.user_type == '1':
            return redirect(reverse("admin_home"))
        elif request.user.user_type == '2':
            return redirect(reverse("staff_home"))
        else:
            return redirect(reverse("student_home"))
    return render(request, 'main_app/login.html')


def doLogin(request, **kwargs):
    if request.method != 'POST':
        return HttpResponse("<h4>Denied</h4>")
    else:
        #Google recaptcha
        captcha_token = request.POST.get('g-recaptcha-response')
        captcha_url = "https://www.google.com/recaptcha/api/siteverify"
        captcha_key = "6LfswtgZAAAAABX9gbLqe-d97qE2g1JP8oUYritJ"
        data = {
            'secret': captcha_key,
            'response': captcha_token
        }
        # Make request
        try:
            captcha_server = requests.post(url=captcha_url, data=data)
            response = json.loads(captcha_server.text)
            if response['success'] == False:
                messages.error(request, 'Invalid Captcha. Try Again')
                return redirect('/')
        except:
            messages.error(request, 'Captcha could not be verified. Try Again')
            return redirect('/')
        
        #Authenticate
        user = EmailBackend.authenticate(request, username=request.POST.get('email'), password=request.POST.get('password'))
        if user != None:
            login(request, user)
            if user.user_type == '1':
                return redirect(reverse("admin_home"))
            elif user.user_type == '2':
                return redirect(reverse("staff_home"))
            else:
                return redirect(reverse("student_home"))
        else:
            messages.error(request, "Invalid details")
            return redirect("/")



def logout_user(request):
    if request.user != None:
        logout(request)
    return redirect("/")


@csrf_exempt
def get_attendance(request):
    subject_id = request.POST.get('subject')
    session_id = request.POST.get('session')
    try:
        subject = get_object_or_404(Subject, id=subject_id)
        session = get_object_or_404(Session, id=session_id)
        attendance = Attendance.objects.filter(subject=subject, session=session)
        attendance_list = []
        for attd in attendance:
            data = {
                    "id": attd.id,
                    "attendance_date": str(attd.date),
                    "session": attd.session.id
                    }
            attendance_list.append(data)
        return JsonResponse(json.dumps(attendance_list), safe=False)
    except Exception as e:
        return None


def showFirebaseJS(request):
    data = """
    // Give the service worker access to Firebase Messaging.
// Note that you can only use Firebase Messaging here, other Firebase libraries
// are not available in the service worker.
importScripts('https://www.gstatic.com/firebasejs/7.22.1/firebase-app.js');
importScripts('https://www.gstatic.com/firebasejs/7.22.1/firebase-messaging.js');

// Initialize the Firebase app in the service worker by passing in
// your app's Firebase config object.
// https://firebase.google.com/docs/web/setup#config-object
firebase.initializeApp({
    apiKey: "AIzaSyBarDWWHTfTMSrtc5Lj3Cdw5dEvjAkFwtM",
    authDomain: "sms-with-django.firebaseapp.com",
    databaseURL: "https://sms-with-django.firebaseio.com",
    projectId: "sms-with-django",
    storageBucket: "sms-with-django.appspot.com",
    messagingSenderId: "945324593139",
    appId: "1:945324593139:web:03fa99a8854bbd38420c86",
    measurementId: "G-2F2RXTL9GT"
});

// Retrieve an instance of Firebase Messaging so that it can handle background
// messages.
const messaging = firebase.messaging();
messaging.setBackgroundMessageHandler(function (payload) {
    const notification = JSON.parse(payload);
    const notificationOption = {
        body: notification.body,
        icon: notification.icon
    }
    return self.registration.showNotification(payload.notification.title, notificationOption);
});
    """
    return HttpResponse(data, content_type='application/javascript')
