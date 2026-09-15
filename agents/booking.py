import os
import asyncio
from typing import Dict, Any, List, Optional
from playwright.async_api import async_playwright, Page, BrowserContext

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


# ---------------------------------------------------------------------------
# 1. ON-SCREEN PROMPT HANDLER (HUMAN-IN-THE-LOOP)
# ---------------------------------------------------------------------------
class AccommodationPromptHandler:
    """Manages CLI prompts and pauses execution cleanly for CAPTCHA & Payment."""

    @staticmethod
    async def prompt_for_captcha(page: Page, timeout_seconds: int = 120) -> bool:
        """Alerts user on screen to solve CAPTCHA/2FA and waits for login success."""
        print("\n" + "=" * 65)
        print("🚨 [ACTION REQUIRED]: SECURITY CHECK / CAPTCHA DETECTED")
        print("   1. Look at the open browser window.")
        print("   2. Solve the CAPTCHA / enter your OTP.")
        print("   3. Click Submit / Complete Login.")
        print("=" * 65 + "\n")

        try:
            # Wait for post-login profile or account button
            await page.wait_for_selector(
                "a[href*='account'], button[aria-label*='Account'], div[data-testid='header-profile']",
                timeout=timeout_seconds * 1000
            )
            print("✅ [STATUS]: Authentication verified! Resuming automation...\n")
            return True
        except Exception:
            print("❌ [ERROR]: Verification wait timed out.\n")
            return False

    @staticmethod
    async def prompt_for_payment_and_wait(page: Page, timeout_seconds: int = 300) -> Dict[str, Any]:
        """Alerts user on screen to pay, then listens for payment completion & Booking ID."""
        print("\n" + "=" * 65)
        print("💳 [ACTION REQUIRED]: PAYMENT / CHECKOUT GATEWAY REACHED")
        print("   1. Complete payment (Credit Card / UPI / PayPal) in the browser.")
        print("   2. Wait for redirection to the booking confirmation screen.")
        print("=" * 65 + "\n")

        try:
            # Listen for confirmation page URLs or booking numbers
            await page.wait_for_url(
                lambda url: "confirmation" in url.lower() or "reserved" in url.lower() or "thankyou" in url.lower(),
                timeout=timeout_seconds * 1000
            )
            await page.wait_for_timeout(3000)  # Buffer for DOM rendering

            # Extract Booking / Confirmation Number
            booking_id = "Captured on Confirmation Page"
            booking_element = await page.query_selector(
                "//*[contains(text(), 'Booking number') or contains(text(), 'Confirmation') or contains(text(), 'Reservation')]/following-sibling::*"
            )
            if booking_element:
                booking_id = await booking_element.inner_text()

            print("=" * 65)
            print(f"🎉 [SUCCESS]: ACCOMMODATION BOOKED | CONFIRMATION ID: {booking_id}")
            print("=" * 65 + "\n")

            return {
                "status": "SUCCESS",
                "confirmation_id": booking_id.strip(),
                "confirmation_url": page.url,
            }
        except Exception as e:
            print(f"❌ [ERROR]: Payment verification timed out. Details: {str(e)}\n")
            return {"status": "TIMEOUT_OR_FAILED", "error": str(e)}


# ---------------------------------------------------------------------------
# 2. PLAYWRIGHT STEALTH ACCOMMODATION ENGINE
# ---------------------------------------------------------------------------
class PlaywrightAccommodationEngine:
    """Manages Playwright browser lifecycle and real-time hotel portal navigation."""

    def __init__(self, user_data_dir: str = "./hotel_playwright_data"):
        self.user_data_dir = user_data_dir
        self.playwright = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def initialize(self):
        """Launches persistent browser context to retain sessions and bypass simple anti-bot checks."""
        if not self.context:
            self.playwright = await async_playwright().start()
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=os.path.abspath(self.user_data_dir),
                headless=False,
                args=[
                    "--start-maximized",
                    "--disable-blink-features=AutomationControlled"
                ],
                viewport={"width": 1280, "height": 800}
            )
            self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()

    async def login_portal(self, login_url: str, username: str, password: str) -> str:
        """Navigates to hotel portal, fills credentials, and hands off CAPTCHA to on-screen prompt."""
        await self.initialize()
        await self.page.goto(login_url, wait_until="domcontentloaded")

        try:
            # Flexible locators for user email/username input
            user_field = await self.page.wait_for_selector(
                "input[type='email'], input[name='username'], input[id='username']", 
                timeout=5000
            )
            if user_field:
                await user_field.fill(username)
                await user_field.press("Enter")
                await self.page.wait_for_timeout(1000)

            # Flexible locators for password input
            pass_field = await self.page.wait_for_selector(
                "input[type='password'], input[name='password']", 
                timeout=5000
            )
            if pass_field:
                await pass_field.fill(password)
                await pass_field.press("Enter")

            # Check if 2FA or CAPTCHA was triggered
            if await AccommodationPromptHandler.prompt_for_captcha(self.page):
                return "Successfully logged into accommodation portal."
            return "Login attempted; manual intervention timed out."
        except Exception as e:
            return f"Login auto-skipped or completed via session cookies. Details: {str(e)}"

    async def search_accommodations(
        self, 
        location: str, 
        checkin_date: str, 
        checkout_date: str, 
        guests: int = 1,
        rooms: int = 1
    ) -> List[Dict[str, Any]]:
        """Executes deep-link search query for real-time inventory on Booking.com."""
        await self.initialize()

        # Direct search URL construction for accurate real-time queries
        search_url = (
            f"https://www.booking.com/searchresults.html?ss={location}"
            f"&checkin={checkin_date}&checkout={checkout_date}"
            f"&group_adults={guests}&no_rooms={rooms}"
        )
        await self.page.goto(search_url, wait_until="networkidle")

        try:
            await self.page.wait_for_selector("div[data-testid='property-card']", timeout=10000)
            cards = await self.page.query_selector_all("div[data-testid='property-card']")

            results = []
            for idx, card in enumerate(cards[:5], start=1):
                name_el = await card.query_selector("div[data-testid='title']")
                price_el = await card.query_selector("span[data-testid='price-and-discounted-price']")
                rating_el = await card.query_selector("div[data-testid='review-score']")

                name = await name_el.inner_text() if name_el else f"Property {idx}"
                price = await price_el.inner_text() if price_el else "See details"
                rating = await rating_el.inner_text() if rating_el else "N/A"

                results.append({
                    "option_index": str(idx),
                    "hotel_name": name.strip(),
                    "price": price.strip(),
                    "rating": rating.split("\n")[0].strip(),
                    "checkin": checkin_date,
                    "checkout": checkout_date
                })
            return results
        except Exception as e:
            return [{"error": f"Failed to retrieve listings: {str(e)}"}]

    async def populate_guest_details_and_checkout(
        self, 
        option_index: str, 
        lead_guest_name: str, 
        lead_guest_email: str
    ) -> str:
        """Selects property card, populates lead guest information, and navigates to payment."""
        await self.initialize()

        cards = await self.page.query_selector_all("div[data-testid='property-card']")
        idx = int(option_index) - 1

        if idx < len(cards):
            title_link = await cards[idx].query_selector("a[data-testid='title-link']")
            
            # Handle new tab navigation if opened
            async with self.context.expect_page() as new_page_info:
                await title_link.click()
            self.page = await new_page_info.value
            await self.page.wait_for_load_state("domcontentloaded")

            # Reserve room button
            reserve_btn = await self.page.wait_for_selector(
                "button:has-text('Reserve'), button:has-text('Select'), button.hp_rt_input", 
                timeout=10000
            )
            if reserve_btn:
                await reserve_btn.click()

            # Fill Guest Details
            first_name = lead_guest_name.split()[0]
            last_name = lead_guest_name.split()[-1] if " " in lead_guest_name else "Guest"

            first_input = await self.page.wait_for_selector("input[name='firstname']", timeout=5000)
            if first_input:
                await first_input.fill(first_name)

            last_input = await self.page.query_selector("input[name='lastname']")
            if last_input:
                await last_input.fill(last_name)

            email_input = await self.page.query_selector("input[name='email']")
            if email_input:
                await email_input.fill(lead_guest_email)

            # Proceed to final step
            submit_btn = await self.page.query_selector("button[name='book']")
            if submit_btn:
                await submit_btn.click()
                await self.page.wait_for_load_state("networkidle")

            return self.page.url
        return "Selected option index out of bounds."

    async def close(self):
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()


# ---------------------------------------------------------------------------
# 3. ORCHESTRATED ACCOMMODATION SUB-AGENT (LANGCHAIN WRAPPER)
# ---------------------------------------------------------------------------
class AccommodationAgentModule:
    """Sub-Agent wrapper structured to accept payload objects from an Orchestrator."""

    def __init__(self, api_key: Optional[str] = None, user_data_dir: str = "./hotel_playwright_data"):
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key

        self.engine = PlaywrightAccommodationEngine(user_data_dir=user_data_dir)
        self.tools = self._bind_tools()
        self.executor = self._build_executor()

    def _bind_tools(self) -> List[Any]:
        engine = self.engine

        @tool
        async def login_accommodation_portal(login_url: str, user_email: str, user_password: str) -> str:
            """Authenticates on the accommodation portal and prompts on-screen for CAPTCHA if needed."""
            return await engine.login_portal(login_url, user_email, user_password)

        @tool
        async def check_accommodation_availability(
            location: str, 
            checkin_date: str, 
            checkout_date: str, 
            guests: int = 1,
            rooms: int = 1
        ) -> str:
            """Searches available hotels/accommodations for specified dates and guest counts."""
            results = await engine.search_accommodations(location, checkin_date, checkout_date, guests, rooms)
            return str(results)

        @tool
        async def navigate_to_hotel_payment(
            option_index: str, 
            lead_guest_name: str, 
            lead_guest_email: str
        ) -> str:
            """Selects room, fills lead guest details, and navigates to the payment/checkout screen."""
            checkout_url = await engine.populate_guest_details_and_checkout(option_index, lead_guest_name, lead_guest_email)
            return f"Navigated to payment checkout page: {checkout_url}."

        @tool
        async def listen_for_hotel_confirmation(timeout_seconds: int = 300) -> str:
            """Prompts user on-screen to make payment, then listens and scrapes final Reservation ID."""
            result = await AccommodationPromptHandler.prompt_for_payment_and_wait(engine.page, timeout_seconds)
            return str(result)

        return [login_accommodation_portal, check_accommodation_availability, navigate_to_hotel_payment, listen_for_hotel_confirmation]

    def _build_executor(self) -> AgentExecutor:
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "You are an automated Accommodation Sub-Agent receiving tasks from a Master Orchestrator.\n\n"
                "Execution Protocol:\n"
                "1. If portal credentials are provided, execute `login_accommodation_portal` first.\n"
                "2. Search hotel availability using `check_accommodation_availability`.\n"
                "3. Select the best match or requested hotel index and call `navigate_to_hotel_payment`.\n"
                "4. Invoke `listen_for_hotel_confirmation` to prompt the user on-screen to complete payment and extract the final Confirmation ID."
            ),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        agent = create_openai_tools_agent(llm, self.tools, prompt)
        return AgentExecutor(agent=agent, tools=self.tools, verbose=True)

    async def run_orchestrated_booking(
        self, 
        location: str, 
        checkin_date: str, 
        checkout_date: str, 
        lead_guest_name: str,
        lead_guest_email: str,
        guests: int = 1,
        rooms: int = 1,
        login_url: Optional[str] = None,
        user_email: Optional[str] = None,
        user_password: Optional[str] = None
    ) -> Dict[str, Any]:
        """Direct invocation point for Master Orchestrator Agent."""
        orchestrator_prompt = (
            f"Execute accommodation booking with the following payload:\n"
            f"- Location: {location}\n"
            f"- Check-in Date (YYYY-MM-DD): {checkin_date}\n"
            f"- Check-out Date (YYYY-MM-DD): {checkout_date}\n"
            f"- Guests: {guests}, Rooms: {rooms}\n"
            f"- Lead Guest Name: {lead_guest_name}\n"
            f"- Lead Guest Email: {lead_guest_email}\n"
        )
        if user_email and user_password and login_url:
            orchestrator_prompt += (
                f"- Portal Login Required: Yes\n"
                f"- Login URL: {login_url}\n"
                f"- User Email: {user_email}\n"
                f"- User Password: {user_password}\n"
            )

        return await self.executor.ainvoke({"input": orchestrator_prompt})

    async def shutdown(self):
        await self.engine.close()


# ---------------------------------------------------------------------------
# 4. EXAMPLE ASYNC INVOCATION
# ---------------------------------------------------------------------------
async def main():
    # Ensure OPENAI_API_KEY environment variable is set
    hotel_agent = AccommodationAgentModule()

    try:
        # Payload passed directly from Master Orchestrator
        response = await hotel_agent.run_orchestrated_booking(
            location="Tirupati",
            checkin_date="2026-11-10",
            checkout_date="2026-11-12",
            guests=2,
            rooms=1,
            lead_guest_name="Dinesh",
            lead_guest_email="dinesh@example.com"
        )
        
        print("\n[ORCHESTRATOR SUB-AGENT OUTPUT]:\n", response["output"])

    finally:
        await hotel_agent.shutdown()


if __name__ == "__main__":
    asyncio.run(main())