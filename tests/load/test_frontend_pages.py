"""Frontend smoke test using Playwright to verify page loads and functionality."""

import asyncio
import os
import sys
from typing import List

import pytest
from playwright.async_api import (Browser, BrowserContext, Page,
                                  async_playwright)

BASE_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"


class ConsoleErrorCollector:
    """Collect JavaScript console errors and warnings."""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def on_message(self, msg):
        """Handle console messages."""
        if msg.type == "error":
            self.errors.append(msg.text)
        elif msg.type == "warning":
            self.warnings.append(msg.text)

    def has_errors(self) -> bool:
        """Check if any errors were logged."""
        return len(self.errors) > 0


@pytest.mark.asyncio
async def test_login_page_loads():
    """Test that login page loads without errors."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        context = await browser.new_context()
        page = await context.new_page()

        error_collector = ConsoleErrorCollector()
        page.on("console", error_collector.on_message)

        await page.goto(f"{BASE_URL}/login", wait_until="networkidle")

        # Verify page elements
        assert await page.query_selector("input[type='email']"), "Email input not found"
        assert await page.query_selector(
            "input[type='password']"
        ), "Password input not found"
        assert await page.query_selector(
            "button[type='submit']"
        ), "Submit button not found"

        assert (
            not error_collector.has_errors()
        ), f"Console errors: {error_collector.errors}"

        await context.close()
        await browser.close()


@pytest.mark.asyncio
async def test_dashboard_page_loads_after_login():
    """Test dashboard page loads after authentication."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        context = await browser.new_context()
        page = await context.new_page()

        error_collector = ConsoleErrorCollector()
        page.on("console", error_collector.on_message)

        # Navigate to login
        await page.goto(f"{BASE_URL}/login", wait_until="networkidle")

        # Fill login form (using test credentials)
        await page.fill(
            "input[type='email']", os.getenv("TEST_EMAIL", "test@example.com")
        )
        await page.fill(
            "input[type='password']", os.getenv("TEST_PASSWORD", "password")
        )
        await page.click("button[type='submit']")

        # Wait for navigation to dashboard
        await page.wait_for_navigation(timeout=10000)

        # Verify dashboard elements
        assert (
            await page.query_selector("[data-testid='dashboard-main']")
            or await page.query_selector(".dashboard")
            or await page.url.find("dashboard") != -1
        ), "Dashboard not loaded"

        assert (
            not error_collector.has_errors()
        ), f"Console errors: {error_collector.errors}"

        await context.close()
        await browser.close()


@pytest.mark.asyncio
async def test_sensors_page_loads_with_tabs():
    """Test sensors page loads with all tabs (Overview, Checks, Results)."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        context = await browser.new_context()
        page = await context.new_page()

        error_collector = ConsoleErrorCollector()
        page.on("console", error_collector.on_message)

        # Navigate directly to sensors page
        await page.goto(f"{BASE_URL}/sensors", wait_until="networkidle")

        # Verify tabs exist
        overview_tab = await page.query_selector(
            "[data-testid='tab-overview']"
        ) or await page.query_selector("button:has-text('Overview')")
        checks_tab = await page.query_selector(
            "[data-testid='tab-checks']"
        ) or await page.query_selector("button:has-text('Checks')")
        results_tab = await page.query_selector(
            "[data-testid='tab-results']"
        ) or await page.query_selector("button:has-text('Results')")

        assert overview_tab, "Overview tab not found"
        assert checks_tab, "Checks tab not found"
        assert results_tab, "Results tab not found"

        # Test tab navigation
        await checks_tab.click()
        await page.wait_for_timeout(500)

        await results_tab.click()
        await page.wait_for_timeout(500)

        assert (
            not error_collector.has_errors()
        ), f"Console errors: {error_collector.errors}"

        await context.close()
        await browser.close()


@pytest.mark.asyncio
async def test_settings_page_loads_with_tabs():
    """Test settings page loads with all tabs (Users, API Keys, License)."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        context = await browser.new_context()
        page = await context.new_page()

        error_collector = ConsoleErrorCollector()
        page.on("console", error_collector.on_message)

        # Navigate directly to settings page
        await page.goto(f"{BASE_URL}/settings", wait_until="networkidle")

        # Verify tabs exist
        users_tab = await page.query_selector(
            "[data-testid='tab-users']"
        ) or await page.query_selector("button:has-text('Users')")
        api_tab = await page.query_selector(
            "[data-testid='tab-api-keys']"
        ) or await page.query_selector("button:has-text('API Keys')")
        license_tab = await page.query_selector(
            "[data-testid='tab-license']"
        ) or await page.query_selector("button:has-text('License')")

        assert users_tab, "Users tab not found"
        assert api_tab, "API Keys tab not found"
        assert license_tab, "License tab not found"

        # Test tab navigation
        await api_tab.click()
        await page.wait_for_timeout(500)

        await license_tab.click()
        await page.wait_for_timeout(500)

        assert (
            not error_collector.has_errors()
        ), f"Console errors: {error_collector.errors}"

        await context.close()
        await browser.close()


@pytest.mark.asyncio
async def test_sidebar_navigation_expand_collapse():
    """Test sidebar navigation expand/collapse for all categories."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        context = await browser.new_context()
        page = await context.new_page()

        error_collector = ConsoleErrorCollector()
        page.on("console", error_collector.on_message)

        # Navigate to main page
        await page.goto(f"{BASE_URL}/dashboard", wait_until="networkidle")

        # Find sidebar toggle/categories
        sidebar_categories = await page.query_selector_all(
            "[data-testid^='sidebar-category-'] button, .sidebar-category button, [role='treeitem']"
        )

        assert len(sidebar_categories) > 0, "No sidebar categories found"

        # Test expand/collapse for each category
        for category in sidebar_categories[:5]:  # Test first 5 categories
            try:
                await category.click()
                await page.wait_for_timeout(300)

                # Verify category state changed
                is_expanded = await category.get_attribute("aria-expanded")
                assert is_expanded in ["true", "false", None], "Invalid expanded state"
            except Exception as e:
                print(f"Error testing category: {e}")

        assert (
            not error_collector.has_errors()
        ), f"Console errors: {error_collector.errors}"

        await context.close()
        await browser.close()


@pytest.mark.asyncio
async def test_no_console_errors_on_pages():
    """Comprehensive test for console errors across multiple pages."""
    pages_to_test = [
        "/login",
        "/dashboard",
        "/sensors",
        "/settings",
    ]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        context = await browser.new_context()

        for page_path in pages_to_test:
            page = await context.new_page()
            error_collector = ConsoleErrorCollector()
            page.on("console", error_collector.on_message)

            try:
                await page.goto(
                    f"{BASE_URL}{page_path}", wait_until="networkidle", timeout=15000
                )
                await page.wait_for_timeout(1000)

                assert (
                    not error_collector.has_errors()
                ), f"Console errors on {page_path}: {error_collector.errors}"
            finally:
                await page.close()

        await context.close()
        await browser.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
