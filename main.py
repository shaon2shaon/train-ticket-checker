from fastapi import FastAPI, Query
from pydantic import BaseModel
from typing import List
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import logging
import time
import smtplib
from email.message import EmailMessage
from fastapi.responses import JSONResponse
import os
from selenium.webdriver.chrome.service import Service


app = FastAPI()

EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")


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

def send_email(subject, body, receiver_email):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = receiver_email
    msg.set_content(body)

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        print("Email sent!")

def check_tickets(
    target_train_name: str = "BANALATA",
    from_city: str = "Dhaka",
    to_city: str = "Rajshahi",
    seat_class: str = "SNIGDHA",
    date: str = "05-Jun-2025",
    receiver_email: str = "kashmisultana@gmail.com"
) -> List[dict]:

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920x1080")
    chrome_options.binary_location = os.environ.get("CHROME_BIN", "/usr/bin/google-chrome-stable")
    
    chrome_options.binary_location = os.getenv("CHROME_PATH", "/usr/bin/chromium")
    service = Service(executable_path=os.getenv("CHROME_DRIVER_PATH", "/usr/bin/chromedriver"))

    driver = webdriver.Chrome(service=service, options=chrome_options)

    url = (
        f'https://eticket.railway.gov.bd/booking/train/search'
        f'?fromcity={from_city}&tocity={to_city}&doj={date}&class={seat_class}'
    )

    results = []

    try:
        driver.get(url)
        WebDriverWait(driver, 20).until(
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

                if receiver_email and train_name.startswith(target_train_name) and seat_type.upper() == seat_class:
                    try:
                        if int(available_tickets) > 0:
                            send_email(
                                subject=f"{target_train_name} {seat_class} Ticket Available!",
                                body=f"{available_tickets} tickets of {date} are available!",
                                receiver_email=receiver_email
                            )
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
    target_train_name: str = Query("BANALATA"),
    from_city: str = Query("Dhaka"),
    to_city: str = Query("Rajshahi"),
    seat_class: str = Query("SNIGDHA"),
    date: str = Query("05-Jun-2025"),
    receiver_email: str = Query("kashmisultana@gmail.com"),
    nocache: str = Query(None)
):
    data = check_tickets(target_train_name, from_city, to_city, seat_class, date, receiver_email)
    return JSONResponse(
        content=data,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )

if __name__ == "__main__":
    check_tickets()
