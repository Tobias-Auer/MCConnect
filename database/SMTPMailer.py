import smtplib
import threading
import queue
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import time

class SMTPMailer:
    def __init__(self, smtp_server, smtp_port, username, password):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.email_queue = queue.Queue()
        self.running = True

        # Starte den SMTP-Worker-Thread
        self.worker_thread = threading.Thread(target=self._smtp_worker, daemon=True)
        self.worker_thread.start()

    def _smtp_worker(self):
        """SMTP-Worker mit persistentem Server, der sich bei Leerlauf nach X Sekunden trennt."""
        server = None
        connected = False
        idle_timeout = 5  # Sekunden ohne neue E-Mails, dann trennen

        while self.running:
            try:
                # Auf neue Mail warten (mit Timeout)
                recipient, subject, text = self.email_queue.get(timeout=idle_timeout)

                # Verbindung aufbauen, falls nicht verbunden
                if not connected:
                    try:
                        server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10)
                        server.starttls()
                        server.login(self.username, self.password)
                        connected = True
                        print("SMTP verbunden.")
                    except Exception as e:
                        print(f"Verbindungsfehler: {e}")
                        self.email_queue.task_done()
                        continue

                # Mail senden
                self._send_email(server, recipient, subject, text)
                self.email_queue.task_done()
                time.sleep(0.8)  # Rate-Limit beachten

            except queue.Empty:
                # Nichts mehr zu tun, Verbindung schließen
                if connected:
                    try:
                        server.quit()
                    except Exception:
                        pass
                    connected = False
                    print("SMTP-Verbindung wegen Leerlauf geschlossen.")


    def _send_email(self, server, recipient, subject, text):
        """Sendet eine E-Mail über eine bestehende SMTP-Verbindung."""
        sender_email = self.username
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = recipient
        msg["Subject"] = subject

        
        # HTML-Inhalt der E-Mail
        html_content = f"""\
        <html>
        <body>
            {text}
        </body>
        </html>
        """
        msg.attach(MIMEText(html_content, "html"))

        try:
            server.sendmail(sender_email, recipient, msg.as_string())
            print(f"E-Mail an {recipient} erfolgreich gesendet!")
        except Exception as e:
            print(f"Fehler beim Senden an {recipient}: {e}")

    def send_email(self, recipient, subject, text):
        """Fügt eine E-Mail zur Warteschlange hinzu."""
        print(f"Füge E-Mail an Warteschlange für {recipient} hinzu.")
        self.email_queue.put((recipient, subject, text))

    def stop(self):
        """Beendet den SMTP-Worker-Thread."""
        self.running = False
        self.email_queue.put((None, None))  # Beenden-Signal für Thread
        self.worker_thread.join()


# Test
if __name__ == "__main__":
    # Lade Zugangsdaten aus Datei
    with open("./database/credentials.txt", "r") as file:
        SMTP_USER = file.readline().strip()
        SMTP_PASS = file.readline().strip()

    mailer = SMTPMailer("smtp.strato.com", 587, SMTP_USER, SMTP_PASS)

    # Mehrere E-Mails versenden (asynchron)
    mailer.send_email("test1@t-auer.com", "1", "Hallo, dies ist eine Nachricht.")
    mailer.send_email("balu.safemail@gmail.com", "test2", "Dritte Nachricht.")

    # Warten, bis alle E-Mails versendet wurden
    mailer.email_queue.join()

    # SMTP-Verbindung beenden
    mailer.stop()
