document.addEventListener('DOMContentLoaded', async () => {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab) {
        document.getElementById('url').value = tab.url;
    }

    document.getElementById('send').addEventListener('click', async () => {
        const note = document.getElementById('note').value;
        const statusDiv = document.getElementById('status');

        statusDiv.textContent = "Sending...";

        const payload = {
            source: "browser",
            source_id: "popup-" + Date.now(),
            content: {
                url: tab.url,
                title: tab.title,
                note: note
            }
        };

        try {
            const response = await fetch("http://localhost:8000/api/v1/context/capture", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                statusDiv.textContent = "Saved!";
                setTimeout(() => window.close(), 1000);
            } else {
                statusDiv.textContent = "Error: " + response.status;
            }
        } catch (e) {
            statusDiv.textContent = "Failed: " + e.message;
        }
    });
});
