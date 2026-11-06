#!/usr/bin/env python3
"""
Playwright E2E Test Suite for:
1. Nutritionist Portal Navigation & Title updates:
   - "Appointments" link in NutriNavbar (pointing to /nutritionist/availability)
   - "Manage Appointments" button on Nutritionist Dashboard
   - "Appointments & Availability" header title and "Appointments & Consultation Schedule" badge on AddAvailability
2. Badge Icons & Tabs on Nutritionist Portal:
   - Horizon tabs: Upcoming, Past, All Slots with icons
   - Mode tabs: All Modes, Virtual, In-Clinic, Both with icons
   - Status tabs: All, Open, Booked with icons
3. Badge Icons & Tabs on Patient Portal (MyAppointments):
   - Horizon tabs: Upcoming, Past, All Appointments with icons
   - Mode tabs: All Modes, Virtual (Zoom), In-Clinic with icons
   - Status tabs: All Status, Confirmed, Under Review, Action Needed, Cancelled with icons
   - Interactive filtering without errors
"""
import os
import sys
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "playwright_screenshots", "navigation_badges")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

FRONTEND_URL = "http://localhost:5173"

def run_tests():
    print("=" * 80)
    print("   PLAYWRIGHT E2E: PORTAL NAVIGATION, TITLES & FILTER BADGES TEST   ")
    print("=" * 80)

    results = []
    def record(name, passed, details=""):
        results.append((name, passed, details))
        mark = "✅ PASS" if passed else "❌ FAIL"
        print(f"{mark} | {name} | {details}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # =========================================================================
        # Test Suite 1: Nutritionist Portal - Appointments Title & Filter Badges
        # =========================================================================
        try:
            print("\n[Suite 1] Nutritionist Portal Navigation & Filter Badges...")
            ctx_nutri = browser.new_context(viewport={"width": 1440, "height": 900})
            page_nutri = ctx_nutri.new_page()

            page_nutri.goto(f"{FRONTEND_URL}/login")
            page_nutri.wait_for_selector("input#login-email, input[type='email']", timeout=10000)
            page_nutri.fill("input#login-email, input[type='email']", "zetroitofficial@gmail.com")
            page_nutri.fill("input#login-password, input[type='password']", "Demo@1234")
            page_nutri.click("button[type='submit']")
            page_nutri.wait_for_url("**/nutritionist**", timeout=15000)
            record("Nutritionist Login", True, f"Navigated to {page_nutri.url}")

            # 1. Check Navbar contains "Appointments" (desktop nav)
            page_nutri.wait_for_selector("nav", timeout=5000)
            nav_links = page_nutri.locator("nav a").all_inner_texts()
            has_appointments_nav = any("Appointments" in t for t in nav_links)
            has_no_old_availability_nav = not any(t.strip() == "Availability" for t in nav_links)
            record("NutriNavbar Shows 'Appointments'", has_appointments_nav and has_no_old_availability_nav,
                   f"Found 'Appointments' link: {has_appointments_nav}, old 'Availability' absent: {has_no_old_availability_nav}")

            # 2. Check Dashboard Quick Link contains "Manage Appointments"
            dashboard_text = page_nutri.inner_text("body")
            has_manage_appointments_btn = "Manage Appointments" in dashboard_text
            record("Dashboard 'Manage Appointments' Button", has_manage_appointments_btn,
                   f"Has 'Manage Appointments': {has_manage_appointments_btn}")

            # Click the Appointments link in navbar
            appt_nav_link = page_nutri.locator("nav a:has-text('Appointments')").first
            appt_nav_link.click()
            page_nutri.wait_for_url("**/nutritionist/availability**", timeout=10000)
            page_nutri.wait_for_timeout(2000)
            page_nutri.screenshot(path=f"{SCREENSHOTS_DIR}/01_nutritionist_appointments_page.png")

            # 3. Check Page Header & Badge Titles
            page_text_lower = page_nutri.inner_text("body").lower()
            has_header_title = "appointments & availability" in page_text_lower
            has_badge_pill = "appointments & consultation schedule" in page_text_lower
            record("AddAvailability Page Header & Badge Title", has_header_title and has_badge_pill,
                   f"Header='Appointments & Availability': {has_header_title}, Badge='Appointments & Consultation Schedule': {has_badge_pill}")

            # 4. Check Horizon filter tabs have icons (svg inside the button)
            upcoming_tab = page_nutri.locator("button:has-text('Upcoming')").first
            past_tab = page_nutri.locator("button:has-text('Past')").first
            all_slots_tab = page_nutri.locator("button:has-text('All Slots')").first

            upcoming_svg = upcoming_tab.locator("svg").count() > 0
            past_svg = past_tab.locator("svg").count() > 0
            all_slots_svg = all_slots_tab.locator("svg").count() > 0

            record("Nutritionist Horizon Filter Tabs Have Badge Icons",
                   upcoming_svg and past_svg and all_slots_svg,
                   f"Upcoming icon: {upcoming_svg}, Past icon: {past_svg}, All Slots icon: {all_slots_svg}")

            # 5. Check Mode filter tabs have icons
            all_modes_btn = page_nutri.locator("button:has-text('All Modes')").first
            virtual_mode_btn = page_nutri.locator("button:has-text('Virtual')").first
            inclinic_mode_btn = page_nutri.locator("button:has-text('In-Clinic')").first

            all_modes_svg = all_modes_btn.locator("svg").count() > 0
            virtual_svg = virtual_mode_btn.locator("svg").count() > 0
            inclinic_svg = inclinic_mode_btn.locator("svg").count() > 0

            record("Nutritionist Mode Filter Tabs Have Icons",
                   all_modes_svg and virtual_svg and inclinic_svg,
                   f"All Modes icon: {all_modes_svg}, Virtual icon: {virtual_svg}, In-Clinic icon: {inclinic_svg}")

            # 6. Check Status filter tabs have badge icons
            all_st_btn = page_nutri.locator("button:has-text('All')").first
            open_st_btn = page_nutri.locator("button:has-text('Open')").first
            booked_st_btn = page_nutri.locator("button:has-text('Booked')").first

            all_st_svg = all_st_btn.locator("svg").count() > 0
            open_st_svg = open_st_btn.locator("svg").count() > 0
            booked_st_svg = booked_st_btn.locator("svg").count() > 0

            record("Nutritionist Status Filter Tabs Have Badge Icons",
                   all_st_svg and open_st_svg and booked_st_svg,
                   f"All icon: {all_st_svg}, Open icon: {open_st_svg}, Booked icon: {booked_st_svg}")

            # 7. Test Tab switching interactivity
            past_tab.click()
            page_nutri.wait_for_timeout(1000)
            page_nutri.screenshot(path=f"{SCREENSHOTS_DIR}/02_nutritionist_past_tab.png")

            upcoming_tab.click()
            page_nutri.wait_for_timeout(1000)
            page_nutri.screenshot(path=f"{SCREENSHOTS_DIR}/03_nutritionist_upcoming_tab.png")
            record("Nutritionist Filter Interactivity", True, "Successfully switched between Upcoming and Past tabs")

            ctx_nutri.close()
        except Exception as e:
            record("Nutritionist Portal Suite", False, str(e))

        # =========================================================================
        # Test Suite 2: Patient Portal - Appointments Filters & Badge Icons
        # =========================================================================
        try:
            print("\n[Suite 2] Patient Portal Appointments Filters & Badge Icons...")
            ctx_patient = browser.new_context(viewport={"width": 1440, "height": 900})
            page_patient = ctx_patient.new_page()

            page_patient.goto(f"{FRONTEND_URL}/login")
            page_patient.wait_for_selector("input#login-email, input[type='email']", timeout=10000)
            page_patient.fill("input#login-email, input[type='email']", "t1@gmail.com")
            page_patient.fill("input#login-password, input[type='password']", "Demo@1234")
            page_patient.click("button[type='submit']")
            page_patient.wait_for_url("**/dashboard**", timeout=15000)
            record("Patient Login", True, f"Navigated to {page_patient.url}")

            # Navigate directly to MyAppointments
            page_patient.goto(f"{FRONTEND_URL}/dashboard/appointments?tab=my-appointments")
            page_patient.wait_for_timeout(3000)
            page_patient.screenshot(path=f"{SCREENSHOTS_DIR}/04_patient_my_appointments_tabs.png")

            # 1. Horizon Filter Tabs have icons
            pat_upcoming = page_patient.locator("button:has-text('Upcoming')").first
            pat_past = page_patient.locator("button:has-text('Past')").first
            pat_all = page_patient.locator("button:has-text('All Appointments')").first

            pat_upcoming_svg = pat_upcoming.locator("svg").count() > 0
            pat_past_svg = pat_past.locator("svg").count() > 0
            pat_all_svg = pat_all.locator("svg").count() > 0

            record("Patient Horizon Filter Tabs Have Badge Icons",
                   pat_upcoming_svg and pat_past_svg and pat_all_svg,
                   f"Upcoming icon: {pat_upcoming_svg}, Past icon: {pat_past_svg}, All icon: {pat_all_svg}")

            # 2. Mode Filter Tabs have icons
            pat_mode_all = page_patient.locator("button:has-text('All Modes')").first
            pat_mode_virtual = page_patient.locator("button:has-text('Virtual')").first
            pat_mode_inclinic = page_patient.locator("button:has-text('In-Clinic')").first

            pat_mode_all_svg = pat_mode_all.locator("svg").count() > 0
            pat_mode_virtual_svg = pat_mode_virtual.locator("svg").count() > 0
            pat_mode_inclinic_svg = pat_mode_inclinic.locator("svg").count() > 0

            record("Patient Mode Filter Tabs Have Badge Icons",
                   pat_mode_all_svg and pat_mode_virtual_svg and pat_mode_inclinic_svg,
                   f"All Modes icon: {pat_mode_all_svg}, Virtual icon: {pat_mode_virtual_svg}, In-Clinic icon: {pat_mode_inclinic_svg}")

            # 3. Status Filter Tabs have icons (All Status, Confirmed, Under Review, Action Needed, Cancelled)
            st_all = page_patient.locator("button:has-text('All Status')").first
            st_confirmed = page_patient.locator("button:has-text('Confirmed')").first
            st_review = page_patient.locator("button:has-text('Under Review')").first
            st_action = page_patient.locator("button:has-text('Action Needed')").first
            st_cancelled = page_patient.locator("button:has-text('Cancelled')").first

            st_all_svg = st_all.locator("svg").count() > 0
            st_confirmed_svg = st_confirmed.locator("svg").count() > 0
            st_review_svg = st_review.locator("svg").count() > 0
            st_action_svg = st_action.locator("svg").count() > 0
            st_cancelled_svg = st_cancelled.locator("svg").count() > 0

            record("Patient Status Filter Tabs Have Badge Icons",
                   st_all_svg and st_confirmed_svg and st_review_svg and st_action_svg and st_cancelled_svg,
                   f"All Status={st_all_svg}, Confirmed={st_confirmed_svg}, Under Review={st_review_svg}, Action Needed={st_action_svg}, Cancelled={st_cancelled_svg}")

            # 4. Interactive Filter Testing
            st_action.click()
            page_patient.wait_for_timeout(1000)
            page_patient.screenshot(path=f"{SCREENSHOTS_DIR}/05_patient_action_needed_filter.png")

            st_confirmed.click()
            page_patient.wait_for_timeout(1000)
            page_patient.screenshot(path=f"{SCREENSHOTS_DIR}/06_patient_confirmed_filter.png")

            pat_all.click()
            page_patient.wait_for_timeout(1000)
            st_all.click()
            page_patient.wait_for_timeout(1000)
            page_patient.screenshot(path=f"{SCREENSHOTS_DIR}/07_patient_all_appointments.png")

            record("Patient Filter Interactivity", True, "Successfully switched between Status and Horizon filters without errors")

            ctx_patient.close()
        except Exception as e:
            record("Patient Portal Suite", False, str(e))

        browser.close()

    print("\n" + "=" * 80)
    print("                     E2E AUDIT EXECUTION SUMMARY                     ")
    print("=" * 80)
    passed_count = sum(1 for _, p, _ in results if p)
    total_count = len(results)
    for name, p, details in results:
        mark = "✅ PASS" if p else "❌ FAIL"
        print(f"[{mark}] {name} -> {details}")
    print(f"\nFinal Score: {passed_count}/{total_count} ({passed_count/total_count*100:.1f}%)")

    if passed_count != total_count:
        sys.exit(1)

if __name__ == "__main__":
    run_tests()

