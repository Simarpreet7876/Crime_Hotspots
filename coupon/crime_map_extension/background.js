chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "getGoogleMapsAPI") {
        const apiKey = "AIzaSyCCzlW7IfXbg8DBBTMimiCn50WjwfOELrA"; // 🔹 Store API key securely

        // Respond to the popup with the API key
        sendResponse({ apiKey: apiKey });
    }
    return true; // Required for asynchronous sendResponse
});
