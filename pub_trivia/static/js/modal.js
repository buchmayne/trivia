// Create modal elements
function createModal() {
    const modalHtml = `
        <div class="modal-overlay" id="modal">
            <div class="modal-content">
                <button class="modal-close">&times;</button>
                <div class="modal-body"></div>
            </div>
        </div>
    `;
    document.body.insertAdjacentHTML('beforeend', modalHtml);

    // Add event listeners
    const modal = document.getElementById('modal');
    const closeButton = modal.querySelector('.modal-close');
    
    closeButton.addEventListener('click', () => {
        modal.style.display = 'none';
    });
    
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.style.display = 'none';
        }
    });

    // Add keyboard support
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modal.style.display === 'block') {
            modal.style.display = 'none';
        }
    });
}

// Show image in modal
function showImageModal(img) {
    const modal = document.getElementById('modal');
    const modalBody = modal.querySelector('.modal-body');
    modalBody.innerHTML = '';
    
    const modalImage = document.createElement('img');
    modalImage.src = img.src;
    modalImage.alt = img.alt;
    modalImage.className = 'modal-image';
    
    modalBody.appendChild(modalImage);
    modal.style.display = 'block';
}

// Show answer text in modal
function showAnswerModal(answer) {
    const modal = document.getElementById('modal');
    const modalBody = modal.querySelector('.modal-body');
    modalBody.innerHTML = '';
    
    const modalText = document.createElement('div');
    modalText.className = 'modal-text';
    modalText.textContent = answer.querySelector('.answer-text').textContent;
    
    modalBody.appendChild(modalText);
    modal.style.display = 'block';
}

// Initialize modal functionality
document.addEventListener('DOMContentLoaded', () => {
    createModal();
    
    // Add click handlers for images
    document.querySelectorAll('.question-image img, .answer-image img').forEach(img => {
        img.addEventListener('click', () => showImageModal(img));
    });
    
    // Add click handlers for answers
    document.querySelectorAll('.answer-item').forEach(answer => {
        answer.addEventListener('click', () => showAnswerModal(answer));
    });
});