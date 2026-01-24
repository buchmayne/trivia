document.addEventListener('DOMContentLoaded', function() {
    const gameOrderInput = document.getElementById('id_game_order');

    if (gameOrderInput) {
        // Function to get the next game order
        const getNextGameOrder = async () => {
            try {
                const response = await fetch('/quiz/next-game-order/');
                const data = await response.json();
                // Only set if field is empty or has default value
                if (data.next_order && (!gameOrderInput.value || gameOrderInput.value === '0' || gameOrderInput.value === '1')) {
                    gameOrderInput.value = data.next_order;
                }
            } catch (error) {
                console.error('Error fetching next game order:', error);
            }
        };

        // Check if this is a new game (add page)
        // In Django admin, the add page doesn't have an object ID in the URL pattern
        const isAddPage = window.location.pathname.includes('/add/');

        // Only auto-fill on the add page
        if (isAddPage) {
            getNextGameOrder();
        }
    }
});
