from fastapi import FastAPI, Query
from pydantic import BaseModel
from typing import List
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import chromedriver_autoinstaller
import logging
import time
import smtplib
from email.message import EmailMessage
from apscheduler.schedulers.background import BackgroundScheduler
import os

app = FastAPI()

EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")

class SeatClass(BaseModel):
    class_: str
    fare: str
    available_tickets: str

class TrainInfo(BaseModel):
    train_name: str
    from_: str
    to: str
    start_time: str
    end_time: str
    duration: str
    classes: List[SeatClass]

def send_email(subject, body):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER
    msg.set_content(body)

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        print("Email sent!")

def check_tickets(
    from_city: str = "Dhaka",
    to_city: str = "Rajshahi",
    seat_class: str = "SNIGDHA",
    date: str = "05-Jun-2025"
) -> List[dict]:
    chromedriver_autoinstaller.install()
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920x1080")
    driver = webdriver.Chrome(options=chrome_options)
    wait_general = 20

    url = (
        f'https://eticket.railway.gov.bd/booking/train/search'
        f'?fromcity={from_city}&tocity={to_city}&doj={date}&class={seat_class}'
    )
    results = []
    try:
        driver.get(url)
        WebDriverWait(driver, wait_general).until(
            EC.presence_of_element_located((By.CLASS_NAME, "single-trip-wrapper"))
        )
        time.sleep(2)
        trains = driver.find_elements(By.CLASS_NAME, "single-trip-wrapper")
        for train in trains:
            train_name = train.find_element(By.TAG_NAME, 'h2').text.strip()
            journey_start_elem = train.find_element(By.CLASS_NAME, "journey-start")
            journey_start_time = journey_start_elem.find_element(By.CLASS_NAME, "journey-date").text.strip()
            journey_start_location = journey_start_elem.find_element(By.CLASS_NAME, "journey-location").text.strip()
            journey_end_elem = train.find_element(By.CLASS_NAME, "journey-end")
            journey_end_time = journey_end_elem.find_element(By.CLASS_NAME, "journey-date").text.strip()
            journey_end_location = journey_end_elem.find_element(By.CLASS_NAME, "journey-location").text.strip()
            journey_duration = train.find_element(By.CLASS_NAME, "journey-duration").text.strip()
            seat_classes = train.find_elements(By.CLASS_NAME, "single-seat-class")
            class_list = []
            for seat in seat_classes:
                seat_type = seat.find_element(By.CLASS_NAME, "seat-class-name").text.strip()
                fare = seat.find_element(By.CLASS_NAME, "seat-class-fare").text.strip()
                available_tickets = seat.find_element(By.CLASS_NAME, "all-seats").text.strip()
                class_list.append({
                    "class_": seat_type,
                    "fare": fare,
                    "available_tickets": available_tickets,
                })
                if train_name.startswith("BANALATA") and seat_type.upper() == "SNIGDHA":
                    try:
                        if int(available_tickets) > 0:
                            send_email("BANALATA SNIGDHA Ticket Available!", f"{available_tickets} tickets of Jun 5, 2025, are available!")
                    except ValueError:
                        logging.warning(f"Invalid ticket number: {available_tickets}")
            results.append({
                "train_name": train_name,
                "from_": journey_start_location,
                "to": journey_end_location,
                "start_time": journey_start_time,
                "end_time": journey_end_time,
                "duration": journey_duration,
                "classes": class_list,
            })
    except Exception as e:
        logging.error(f"Error occurred: {e}")
    finally:
        driver.quit()
    return results

@app.get("/", response_model=List[TrainInfo])
def get_trains(
    from_city: str = Query("Dhaka"),
    to_city: str = Query("Rajshahi"),
    seat_class: str = Query("SNIGDHA"),
    date: str = Query("05-Jun-2025")
):
    return check_tickets(from_city, to_city, seat_class, date)

scheduler = BackgroundScheduler()
scheduler.add_job(check_tickets, "interval", minutes=10)
scheduler.start()

@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()

if __name__ == "__main__":
    check_tickets()
