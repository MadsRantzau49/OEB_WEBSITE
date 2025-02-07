// Operate with the server and triggered when a push messages is send.
self.addEventListener("push", async (messageData) => {
  const message = messageData.data ? await messageData.data.text() : "No data";
  const options = {
      body: message,
      icon: './images/rejer.png',
      badge: './images/rejer.png'
  };
  // Send the push to the user.
  await self.registration.showNotification("Rantzau", options);
});
