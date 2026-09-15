#import os
#import pickle
#import time
#from typing import Dict, Any, List, Optional
#from selenium import webdriver
#from selenium.webdriver.common.by import By
#from selenium.webdriver.chrome.service import Service
#from selenium.webdriver.support.ui import WebDriverWait
#from selenium.webdriver.support import expected_conditions as EC
#from webdriver_manager.chrome import ChromeDriverManager
#from selenium_stealth import stealth
#
#from langchain_openai import ChatOpenAI
#from langchain_core.tools import tool
#from langchain.agents import AgentExecutor, create_openai_tools_agent
#from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
#
#
#class StealthTransportBrowser:
#    """Manages browser lifecycle, stealth parameters, and automation actions."""
#    
#    def __init__(self, user_data_dir: str = "./chrome_user_data"):
#        self.user_data_dir = user_data_dir
#        self._driver: Optional[webdriver.Chrome] = None
#        self._wait: Optional[WebDriverWait] = None
#
#    @property
#    def driver(self) -> webdriver.Chrome:
#        """Lazy initialization of Chrome Driver."""
#        if self._driver is None:
#            options = webdriver.ChromeOptions()
#            options.add_argument(f"--user-data-dir={os.path.abspath(self.user_data_dir)}")
#            options.add_argument("--profile-directory=Default")
#            options.add_argument("--start-maximized")
#            options.add_argument("--disable-blink-features=AutomationControlled")
#            options.add_experimental_option("excludeSwitches", ["enable-automation"])
#            options.add_experimental_option("useAutomationExtension", False)
#            options.add_experimental_option("detach", True)
#
#            self._driver = webdriver.Chrome(
#                service=Service(ChromeDriverManager().install()), 
#                options=options
#            )
#            
#            stealth(
#                self._driver,
#                languages=["en-US", "en"],
#                vendor="Google Inc.",
#                platform="Win32",
#                webgl_vendor="Intel Inc.",
#                renderer="Intel Iris OpenGL Engine",
#                fix_hairline=True,
#            )
#            self._wait = WebDriverWait(self._driver, 15)
#        return self._driver
#
#    @property
#    def wait(self) -> WebDriverWait:
#        if self._wait is None:
#            _ = self.driver
#        return self._wait
#
#    def close(self):
#        """Closes browser driver session cleanly."""
#        if self._driver:
#            self._driver.quit()
#            self._driver = None
#            self._wait = None
#
#    def save_cookies(self, cookie_file: str = "session_cookies.pkl") -> str:
#        with open(cookie_file, "wb") as f:
#            pickle.dump(self.driver.get_cookies(), f)
#        return "Cookies saved to disk."
#
#    def load_cookies(self, target_url: str, cookie_file: str = "session_cookies.pkl") -> str:
#        if not os.path.exists(cookie_file):
#            return "No saved cookie file found. Perform manual login once."
#        
#        self.driver.get(target_url)
#        with open(cookie_file, "rb") as f:
#            cookies = pickle.load(f)
#            for cookie in cookies:
#                cookie.pop("sameSite", None)
#                try:
#                    self.driver.add_cookie(cookie)
#                except Exception:
#                    pass
#        self.driver.refresh()
#        return "Session cookies loaded successfully."
#
#    def search_transport(self, origin: str, destination: str, date: str) -> List[Dict[str, str]]:
#        demo_url = "https://blazedemo.com"
#        self.driver.get(demo_url)
#        
#        from_select = self.wait.until(EC.presence_of_element_located((By.NAME, "fromPort")))
#        from_select.send_keys(origin)
#        
#        to_select = self.driver.find_element(By.NAME, "toPort")
#        to_select.send_keys(destination)
#        
#        search_btn = self.driver.find_element(By.XPATH, "//input[@type='submit']")
#        search_btn.click()
#        
#        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
#        rows = self.driver.find_elements(By.XPATH, "//table/tbody/tr")
#        
#        available_options = []
#        for index, row in enumerate(rows, start=1):
#            cols = row.find_elements(By.TAG_NAME, "td")
#            if cols:
#                available_options.append({
#                    "option_index": str(index),
#                    "identifier": cols[1].text if len(cols) > 1 else f"Option {index}",
#                    "provider": cols[2].text if len(cols) > 2 else "Transport",
#                    "price": cols[5].text if len(cols) > 5 else "$50"
#                })
#        return available_options
#
#    def automate_to_payment(self, option_index: str, passenger_name: str) -> str:
#        choose_btn = self.wait.until(
#            EC.element_to_be_clickable((By.XPATH, f"//table/tbody/tr[{option_index}]//input[@type='submit']"))
#        )
#        choose_btn.click()
#        
#        name_input = self.wait.until(EC.presence_of_element_located((By.ID, "inputName")))
#        name_input.clear()
#        name_input.send_keys(passenger_name)
#        
#        purchase_btn = self.driver.find_element(By.XPATH, "//input[@value='Purchase Flight']")
#        purchase_btn.click()
#        time.sleep(2)
#        return self.driver.current_url
#
#    def wait_for_payment_and_scrape_receipt(self, timeout_seconds: int = 300) -> Dict[str, Any]:
#        """
#        Polls the browser until payment is completed, then scrapes booking details.
#        
#        Parameters:
#            timeout_seconds: Maximum time (in seconds) to wait for user to complete manual payment (default: 5 min).
#        """
#        print(f"\n[LISTENER] Waiting up to {timeout_seconds} seconds for manual payment completion...")
#        
#        # Extended wait specifically for manual payment completion
#        payment_wait = WebDriverWait(self.driver, timeout_seconds)
#        
#        try:
#            # Wait until a success condition occurs:
#            # Option A: URL changes to confirmation page (e.g., contains 'confirmation', 'success', 'pnr')
#            # Option B: Target confirmation element appears in DOM
#            payment_wait.until(
#                lambda driver: "confirmation" in driver.current_url.lower() 
#                or "success" in driver.current_url.lower()
#                or len(driver.find_elements(By.XPATH, "//*[contains(text(), 'Thank you') or contains(text(), 'Booking Id') or contains(text(), 'PNR')]")) > 0
#            )
#            
#            time.sleep(2)  # Short pause to let receipt details render fully
#            
#            # Scrape booking details from the confirmation DOM
#            # (Note: Update XPaths according to your specific target provider)
#            receipt_data = {
#                "status": "SUCCESS",
#                "confirmation_url": self.driver.current_url,
#                "booking_id": None,
#                "amount_paid": None,
#                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
#            }
#            
#            # Scrape Booking ID / PNR if present
#            id_elements = self.driver.find_elements(By.XPATH, "//tr[td[contains(text(), 'Id') or contains(text(), 'PNR')]]/td[2]")
#            if id_elements:
#                receipt_data["booking_id"] = id_elements[0].text
#            else:
#                # Fallback: Scrape full receipt text for parsing
#                body_element = self.driver.find_element(By.TAG_NAME, "body")
#                receipt_data["summary_text"] = body_element.text[:500]  # First 500 chars snippet
#                
#            return receipt_data
#
#        except Exception as e:
#            return {
#                "status": "FAILED_OR_TIMEOUT",
#                "error": f"Payment completion was not detected within {timeout_seconds} seconds. Details: {str(e)}"
#            }
#
#
#class TransportAgentModule:
#    """Wrapper class packaging agent tools, LLM executor, and stealth browser."""
#    
#    def __init__(self, api_key: Optional[str] = None, user_data_dir: str = "./chrome_user_data"):
#        if api_key:
#            os.environ["OPENAI_API_KEY"] = api_key
#
#        self.browser = StealthTransportBrowser(user_data_dir=user_data_dir)
#        self.tools = self._bind_tools()
#        self.executor = self._build_executor()
#
#    def _bind_tools(self) -> List[Any]:
##        browser_inst = self.browser
#
 #       @tool
 #       def load_session_cookies(url: str) -> str:
 #           """Loads saved login cookies into the stealth browser session."""
 #           return browser_inst.load_cookies(url)
#
 #       @tool
 #       def save_session_cookies() -> str:
 #           """Saves active browser session cookies for future automated runs."""
 #           return browser_inst.save_cookies()
#
 #       @tool
 #       def stealth_check_availability(origin: str, destination: str, date: str) -> str:
 #           """Uses stealth browser to perform real-time transport searches."""
 #           results = browser_inst.search_transport(origin, destination, date)
 #           return str(results)
#
 #       @tool
 #       def stealth_navigate_to_payment(option_index: str, passenger_name: str) -> str:
 #           """Populates passenger details and proceeds to payment gateway screen."""
 #           payment_url = browser_inst.automate_to_payment(option_index, passenger_name)
 #           return f"Navigated to payment page: {payment_url}. Prompt user to pay, then invoke `listen_for_payment_confirmation`."
#
 #       @tool
 #       def listen_for_payment_confirmation(timeout_seconds: int = 300) -> str:
 #           """Waits for the user to manually finish payment on the browser and then scrapes the final PNR/receipt."""
 #           result = browser_inst.wait_for_payment_and_scrape_receipt(timeout_seconds=timeout_seconds)
 #           return str(result)
#
 #       return [
 #           load_session_cookies, 
 #           save_session_cookies, 
 #           stealth_check_availability, 
 #           stealth_navigate_to_payment,
 #           listen_for_payment_confirmation
 #       ]
#
 #   def _build_executor(self) -> AgentExecutor:
 #       prompt = ChatPromptTemplate.from_messages([
 #           (
 #               "system",
 #               "You are a specialized sub-agent for transport booking automation. "
 #               "You search options, fill forms, and guide users to payment.\n"
 #               "When you land on the payment screen, prompt the user to complete payment manually "
 #               "and trigger `listen_for_payment_confirmation` to confirm receipt and extract the PNR."
 #           ),
 #           MessagesPlaceholder(variable_name="chat_history", optional=True),
 #           ("human", "{input}"),
 #           MessagesPlaceholder(variable_name="agent_scratchpad"),
 #       ])
 #       
 #       llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
 #       agent = create_openai_tools_agent(llm, self.tools, prompt)
 #       return AgentExecutor(agent=agent, tools=self.tools, verbose=True)
#
 #   def run(self, input_text: str, chat_history: Optional[List[Any]] = None) -> Dict[str, Any]:
 #       payload = {"input": input_text}
 #       if chat_history:
 #           payload["chat_history"] = chat_history
 #       return self.executor.invoke(payload)
#
 #   def shutdown(self):
 #       self.browser.close()
#
import os
import time
from typing import Dict, Any, List, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium_stealth import stealth

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


# ---------------------------------------------------------------------------
# 1. STATION CODE RESOLVER MAPPING
# ---------------------------------------------------------------------------
STATION_CODES = {
    "visakhapatnam": "VSKP",
    "vizag": "VSKP",
    "tirupati": "TPTY",
    "hyderabad": "SC",
    "secunderabad": "SC",
    "bengaluru": "SBC",
    "bangalore": "SBC",
    "chennai": "MAS",
    "delhi": "NDLS",
    "mumbai": "CSMT",
    "kolkata": "HWH"
}


# ---------------------------------------------------------------------------
# 2. ON-SCREEN PROMPT HANDLER (HUMAN-IN-THE-LOOP)
# ---------------------------------------------------------------------------
class OnScreenPromptHandler:
    """Manages CLI prompts and pauses execution cleanly for CAPTCHA & Payment."""

    @staticmethod
    def prompt_for_captcha(driver: webdriver.Chrome, timeout_seconds: int = 120) -> bool:
        """Alerts user on screen to solve CAPTCHA/OTP and waits for login success."""
        print("\n" + "=" * 65)
        print("🚨 [ACTION REQUIRED]: CAPTCHA / 2FA DETECTED")
        print("   1. Open the active Chrome window.")
        print("   2. Solve the CAPTCHA / enter the OTP.")
        print("   3. Click the Submit / Login button.")
        print("=" * 65 + "\n")

        try:
            WebDriverWait(driver, timeout_seconds).until(
                EC.presence_of_element_located((
                    By.XPATH, 
                    "//a[contains(text(),'LOGOUT')] | //span[contains(@class, 'user-name')]"
                ))
            )
            print("✅ [STATUS]: Login verified! Resuming automation...\n")
            return True
        except Exception:
            print("❌ [ERROR]: Login wait timed out.\n")
            return False

    @staticmethod
    def prompt_for_payment_and_wait(driver: webdriver.Chrome, timeout_seconds: int = 300) -> Dict[str, Any]:
        """Alerts user on screen to pay, then listens for payment completion & PNR."""
        print("\n" + "=" * 65)
        print("💳 [ACTION REQUIRED]: PAYMENT GATEWAY REACHED")
        print("   1. Complete the payment (UPI / NetBanking / Card) in the browser.")
        print("   2. Wait for IRCTC to redirect back to the confirmation screen.")
        print("=" * 65 + "\n")

        wait = WebDriverWait(driver, timeout_seconds)
        try:
            wait.until(
                lambda d: "booking/reviewBooking" in d.current_url 
                or len(d.find_elements(By.XPATH, "//*[contains(text(), 'PNR')]")) > 0
            )
            time.sleep(3)  # Brief buffer for DOM rendering

            pnr_elements = driver.find_elements(
                By.XPATH, "//span[contains(@class, 'pnr-bold') or contains(text(), 'PNR')]"
            )
            pnr_number = pnr_elements[0].text if pnr_elements else "Captured on Confirmation Page"

            print("=" * 65)
            print(f"🎉 [SUCCESS]: BOOKING CONFIRMED | PNR: {pnr_number}")
            print("=" * 65 + "\n")

            return {
                "status": "SUCCESS",
                "pnr": pnr_number,
                "confirmation_url": driver.current_url,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        except Exception as e:
            print(f"❌ [ERROR]: Payment verification timed out. Details: {str(e)}\n")
            return {"status": "TIMEOUT_OR_FAILED", "error": str(e)}


# ---------------------------------------------------------------------------
# 3. STEALTH IRCTC BROWSER AUTOMATION ENGINE
# ---------------------------------------------------------------------------
class IRCTCTransportBrowser:
    """Manages Selenium Stealth driver lifecycle, IRCTC forms, and DOM actions."""

    def __init__(self, user_data_dir: str = "./irctc_chrome_data"):
        self.user_data_dir = user_data_dir
        self._driver: Optional[webdriver.Chrome] = None
        self._wait: Optional[WebDriverWait] = None

    @property
    def driver(self) -> webdriver.Chrome:
        if self._driver is None:
            options = webdriver.ChromeOptions()
            options.add_argument(f"--user-data-dir={os.path.abspath(self.user_data_dir)}")
            options.add_argument("--profile-directory=Default")
            options.add_argument("--start-maximized")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)
            options.add_experimental_option("detach", True)

            self._driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()), 
                options=options
            )
            
            stealth(
                self._driver,
                languages=["en-US", "en"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True,
            )
            self._wait = WebDriverWait(self._driver, 20)
        return self._driver

    @property
    def wait(self) -> WebDriverWait:
        if self._wait is None:
            _ = self.driver
        return self._wait

    def resolve_station(self, name: str) -> str:
        clean = name.strip().lower()
        return STATION_CODES.get(clean, name.upper())

    def login_user(self, username: str, password: str) -> str:
        """Navigates to IRCTC, enters credentials, and handoffs CAPTCHA to on-screen prompt."""
        self.driver.get("https://www.irctc.co.in/nget/train-search")
        
        login_btn = self.wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(),'LOGIN')]")))
        login_btn.click()

        user_input = self.wait.until(EC.presence_of_element_located((By.XPATH, "//input[@formcontrolname='userid']")))
        user_input.clear()
        user_input.send_keys(username)

        pass_input = self.driver.find_element(By.XPATH, "//input[@formcontrolname='password']")
        pass_input.clear()
        pass_input.send_keys(password)

        # Trigger On-screen Prompt for CAPTCHA / 2FA
        if OnScreenPromptHandler.prompt_for_captcha(self.driver):
            return "Logged in successfully."
        return "Login failed or timed out during CAPTCHA entry."

    def search_trains_flexible(
        self, 
        origin: str, 
        destination: str, 
        journey_date: str, 
        preferred_time: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Searches available trains between station codes on IRCTC.
        Format for journey_date: 'DD/MM/YYYY' (e.g., '15/10/2026')
        """
        origin_code = self.resolve_station(origin)
        dest_code = self.resolve_station(destination)

        self.driver.get("https://www.irctc.co.in/nget/train-search")
        time.sleep(2)

        # Fill Origin
        from_input = self.wait.until(EC.presence_of_element_located((By.XPATH, "//p-autocomplete[@id='origin']//input")))
        from_input.clear()
        from_input.send_keys(origin_code)
        time.sleep(1)
        from_input.send_keys(Keys.ENTER)

        # Fill Destination
        to_input = self.driver.find_element(By.XPATH, "//p-autocomplete[@id='destination']//input")
        to_input.clear()
        to_input.send_keys(dest_code)
        time.sleep(1)
        to_input.send_keys(Keys.ENTER)

        # Fill Journey Date
        date_input = self.driver.find_element(By.XPATH, "//p-calendar[@id='jDate']//input")
        date_input.send_keys(Keys.CONTROL + "a")
        date_input.send_keys(Keys.BACKSPACE)
        date_input.send_keys(journey_date)
        date_input.send_keys(Keys.ENTER)

        # Click Search
        search_btn = self.driver.find_element(By.XPATH, "//button[contains(@class, 'search_btn')]")
        search_btn.click()

        # Scrape Available Train Options
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "train-heading")))
        train_cards = self.driver.find_elements(By.CLASS_NAME, "train-heading")

        results = []
        for idx, card in enumerate(train_cards[:5], start=1):
            text = card.text.split("\n")[0] if card.text else f"Train {idx}"
            results.append({
                "option_index": str(idx),
                "train_name_number": text,
                "origin": origin_code,
                "destination": dest_code,
                "date": journey_date,
                "requested_time": preferred_time or "Flex/Anytime"
            })
        return results

    def populate_passenger_and_checkout(
        self, 
        option_index: str, 
        passenger_name: str, 
        travel_class: str = "SL"
    ) -> str:
        """Selects train option, populates passenger details, and stops at payment gateway."""
        # Click on class tab (SL / 3A / 2A) and Book Now
        train_xpath = f"(//div[contains(@class, 'form-group')])[{option_index}]"
        class_btn = self.wait.until(
            EC.element_to_be_clickable((By.XPATH, f"{train_xpath}//div[contains(text(), '{travel_class}')]"))
        )
        class_btn.click()
        
        book_btn = self.wait.until(
            EC.element_to_be_clickable((By.XPATH, f"{train_xpath}//button[contains(text(), 'Book Now')]"))
        )
        book_btn.click()

        # Fill Passenger Info
        name_field = self.wait.until(
            EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Passenger Name']"))
        )
        name_field.clear()
        name_field.send_keys(passenger_name)

        # Submit to Payment Screen
        continue_btn = self.driver.find_element(By.XPATH, "//button[contains(text(),'Continue')]")
        continue_btn.click()
        time.sleep(2)
        return self.driver.current_url

    def close(self):
        if self._driver:
            self._driver.quit()
            self._driver = None


# ---------------------------------------------------------------------------
# 4. ORCHESTRATED SUB-AGENT MODULE (LANGCHAIN WRAPPER)
# ---------------------------------------------------------------------------
class IRCTCTransportAgentModule:
    """Sub-Agent wrapper structured to accept payload objects from an Orchestrator."""

    def __init__(self, api_key: Optional[str] = None, user_data_dir: str = "./irctc_chrome_data"):
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key

        self.browser = IRCTCTransportBrowser(user_data_dir=user_data_dir)
        self.tools = self._bind_tools()
        self.executor = self._build_executor()

    def _bind_tools(self) -> List[Any]:
        browser = self.browser

        @tool
        def login_irctc(user_username: str, user_password: str) -> str:
            """Authenticates on IRCTC and prompts user on-screen for CAPTCHA/2FA."""
            return browser.login_user(user_username, user_password)

        @tool
        def check_train_availability(
            origin: str, 
            destination: str, 
            journey_date: str, 
            preferred_time: str = ""
        ) -> str:
            """Searches available trains on IRCTC for the journey date and time."""
            results = browser.search_trains_flexible(origin, destination, journey_date, preferred_time)
            return str(results)

        @tool
        def navigate_to_payment(option_index: str, passenger_name: str, travel_class: str = "SL") -> str:
            """Fills passenger details and navigates to the payment gateway."""
            payment_url = browser.populate_passenger_and_checkout(option_index, passenger_name, travel_class)
            return f"Navigated to payment gateway: {payment_url}."

        @tool
        def listen_for_pnr_confirmation(timeout_seconds: int = 300) -> str:
            """Prompts user on-screen to make payment, then listens and scrapes the final PNR."""
            result = OnScreenPromptHandler.prompt_for_payment_and_wait(browser.driver, timeout_seconds)
            return str(result)

        return [login_irctc, check_train_availability, navigate_to_payment, listen_for_pnr_confirmation]

    def _build_executor(self) -> AgentExecutor:
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "You are an automated IRCTC Transport Sub-Agent receiving tasks from a Master Orchestrator.\n\n"
                "Execution Protocol:\n"
                "1. If credentials (username/password) are provided, execute `login_irctc` first.\n"
                "2. Search availability using `check_train_availability` with requested date & preferred time.\n"
                "3. If exact requested time is full, evaluate closer alternative schedules and report back.\n"
                "4. Proceed to payment using `navigate_to_payment`.\n"
                "5. Invoke `listen_for_pnr_confirmation` to prompt user for payment and scrape the generated PNR."
            ),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        agent = create_openai_tools_agent(llm, self.tools, prompt)
        return AgentExecutor(agent=agent, tools=self.tools, verbose=True)

    def run_orchestrated_booking(
        self, 
        origin: str, 
        destination: str, 
        journey_date: str, 
        journey_time: str, 
        passenger_name: str,
        travel_class: str = "SL",
        user_username: Optional[str] = None,
        user_password: Optional[str] = None
    ) -> Dict[str, Any]:
        """Direct invocation point for Master Orchestrator Agent."""
        orchestrator_prompt = (
            f"Execute train booking with the following payload:\n"
            f"- Origin: {origin}\n"
            f"- Destination: {destination}\n"
            f"- Journey Date (DD/MM/YYYY): {journey_date}\n"
            f"- Preferred Journey Time: {journey_time} (pick closest available if exact slot full)\n"
            f"- Travel Class: {travel_class}\n"
            f"- Passenger Name: {passenger_name}\n"
        )
        if user_username and user_password:
            orchestrator_prompt += (
                f"- IRCTC Username: {user_username}\n"
                f"- IRCTC Password: {user_password}\n"
            )

        return self.executor.invoke({"input": orchestrator_prompt})

    def shutdown(self):
        self.browser.close()


# ---------------------------------------------------------------------------
# 5. EXAMPLE USAGE / INVOCATION
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Ensure OPENAI_API_KEY environment variable is set
    agent_module = IRCTCTransportAgentModule()

    try:
        # Example payload from Master Orchestrator
        response = agent_module.run_orchestrated_booking(
            origin="Visakhapatnam",
            destination="Tirupati",
            journey_date="15/10/2026",
            journey_time="10:00 PM",
            passenger_name="Dinesh Polamarasetty",
            travel_class="SL",
            user_username="my_irctc_user",    # Optional
            user_password="my_irctc_password"  # Optional
        )
        
        print("\n[ORCHESTRATOR SUB-AGENT OUTPUT]:\n", response["output"])

    finally:
        agent_module.shutdown()