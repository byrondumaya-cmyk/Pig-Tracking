import re
import urllib.request
from playwright.sync_api import Page, expect

def test_dashboard_loads(page: Page, flask_server: str):
    """Test that the main dashboard loads."""
    page.goto(flask_server, wait_until="domcontentloaded")
    
    # Check title
    expect(page).to_have_title(re.compile("Swine Monitor"))
    
    # Check that main headers exist
    expect(page.locator("text=Swine Monitor AI").first).to_be_visible()
    expect(page.locator("text=RGB Live Feed")).to_be_visible()

def test_settings_auth_required(page: Page, flask_server: str):
    """Test that the settings page requires authentication."""
    response = page.goto(f"{flask_server}/settings", wait_until="domcontentloaded")
    # Should get a 401 Unauthorized
    assert response.status == 401

def test_settings_auth_success(page: Page, flask_server: str):
    """Test successful authentication to settings."""
    # Provide Basic Auth credentials in the URL
    url_with_auth = flask_server.replace("http://", "http://admin:pigtracking123@")
    
    page.goto(f"{url_with_auth}/settings", wait_until="domcontentloaded")
    
    # Check title
    expect(page).to_have_title(re.compile("Settings"))
    
    # Check Settings tabs exist
    expect(page.locator("text=Alert Rules").first).to_be_visible()
    expect(page.locator("text=Contacts").first).to_be_visible()
    expect(page.locator("text=System").first).to_be_visible()

def test_navigation(page: Page, flask_server: str):
    """Test navigating around the dashboard."""
    url_with_auth = flask_server.replace("http://", "http://admin:pigtracking123@")
    page.goto(url_with_auth, wait_until="domcontentloaded")
    
    # Click Settings link
    page.click(".topnav__actions a:has-text('Settings')")
    
    # Verify we are on settings page
    expect(page.locator("text=System Settings").first).to_be_visible()
    
    # Click Back to Dashboard
    page.click("a:has-text('Back to Dashboard')")
    expect(page.locator("text=RGB Live Feed")).to_be_visible()
