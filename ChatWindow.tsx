try {
    // Your code logic here
} catch (error) {
    setChatError(error.message);
    setMessages(prev => [...prev, { text: error.message, type: 'error' }]);
}