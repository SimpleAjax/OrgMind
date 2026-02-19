// background.js

const API_URL = "http://localhost:8000/api/v1/context/capture";

// Simple throttling to avoid spamming API on every scroll/update
let lastCaptureTime = 0;
const CAPTURE_INTERVAL_MS = 2000;

async function captureContext(tab) {
    if (!tab || !tab.url || tab.url.startsWith("chrome://")) return;

    const now = Date.now();
    if (now - lastCaptureTime < CAPTURE_INTERVAL_MS) return;
    lastCaptureTime = now;

    const payload = {
        source: "browser",
        source_id: tab.id.toString(), // Tab ID as source ID? Or URL hash?
        content: {
            url: tab.url,
            title: tab.title,
            favIconUrl: tab.favIconUrl
        },
        // Generate session_id or user_id from storage if available
        // user_id: ...
    };

    try {
        const response = await fetch(API_URL, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            console.log("Context captured:", tab.title);
        } else {
            console.error("Failed to capture context:", response.status);
        }
    } catch (error) {
        console.error("Error capturing context:", error);
    }
}

chrome.tabs.onActivated.addListener(async (activeInfo) => {
    try {
        const tab = await chrome.tabs.get(activeInfo.tabId);
        captureContext(tab);
    } catch (e) {
        console.error("Tab get failed", e);
    }
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (changeInfo.status === 'complete') {
        captureContext(tab);
    }
});
