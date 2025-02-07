// Register the service worker if it is compatible with the browser/device.
if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/static/javascript/serviceWorker.js");
} else {
    console.log("du kan ikke downloade den som APP");
}
