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
    const modalContent = modal.querySelector('.modal-content');
    
    // Clear previous content
    modalBody.innerHTML = '';
    
    // Add class for text-specific styling
    modalContent.classList.add('text-modal');
    
    const modalText = document.createElement('div');
    modalText.className = 'modal-text';
    modalText.textContent = answer.querySelector('.answer-text').textContent;
    
    modalBody.appendChild(modalText);
    modal.style.display = 'block';
    
    // Clean up when modal closes
    const cleanup = () => {
        modalContent.classList.remove('text-modal');
    };
    
    // Add cleanup to existing close handlers
    modal.querySelector('.modal-close').addEventListener('click', cleanup, { once: true });
    modal.addEventListener('click', (e) => {
        if (e.target === modal) cleanup();
    }, { once: true });
}

function showAnswerBankModal(answerBank) {
    const modal = document.getElementById('modal');
    const modalBody = modal.querySelector('.modal-body');
    const modalContent = modal.querySelector('.modal-content');
    
    // Clear previous content
    modalBody.innerHTML = '';
    
    // Add class for text-specific styling
    modalContent.classList.add('text-modal');
    
    const modalAnswerBank = document.createElement('div');
    modalAnswerBank.className = 'modal-answer-bank';
    
    // Create title
    const title = document.createElement('h2');
    title.className = 'answer-bank-title';
    title.textContent = 'Answer Bank';
    
    // Create content
    const content = document.createElement('div');
    content.className = 'answer-bank-content';
    content.innerHTML = answerBank.querySelector('.answer-bank-content').innerHTML;
    
    modalAnswerBank.appendChild(title);
    modalAnswerBank.appendChild(content);
    modalBody.appendChild(modalAnswerBank);
    modal.style.display = 'block';
    
    // Clean up when modal closes
    const cleanup = () => {
        modalContent.classList.remove('text-modal');
    };
    
    modal.querySelector('.modal-close').addEventListener('click', cleanup, { once: true });
    modal.addEventListener('click', (e) => {
        if (e.target === modal) cleanup();
    }, { once: true });
}


// Show video in modal
function showVideoModal(video) {
    const modal = document.getElementById('modal');
    const modalBody = modal.querySelector('.modal-body');
    modalBody.innerHTML = '';
    
    const modalVideo = document.createElement('video');
    modalVideo.src = video.src;
    modalVideo.controls = true;
    modalVideo.className = 'modal-video';
    modalVideo.autoplay = false; // Don't autoplay in modal
    
    // Copy all source elements for format compatibility
    const sources = video.querySelectorAll('source');
    sources.forEach(source => {
        const newSource = document.createElement('source');
        newSource.src = source.src;
        newSource.type = source.type;
        modalVideo.appendChild(newSource);
    });
    
    modalBody.appendChild(modalVideo);
    modal.style.display = 'block';
}

// Initialize modal functionality
document.addEventListener('DOMContentLoaded', () => {
    createModal();
    
    // Add click handlers for question images
    document.querySelectorAll('.question-image img').forEach(img => {
        img.addEventListener('click', (e) => {
            e.stopPropagation(); // Prevent event bubbling
            showImageModal(img);
        });
    });
    
    // Add click handlers for answer images
    document.querySelectorAll('.answer-image img').forEach(img => {
        img.addEventListener('click', (e) => {
            e.stopPropagation(); // Prevent event bubbling
            showImageModal(img);
        });
    });

    // New video handlers
    document.querySelectorAll('.question-video video').forEach(video => {
        video.addEventListener('click', (e) => {
            e.stopPropagation();
            showVideoModal(video);
        });
    });
    
    document.querySelectorAll('.answer-video video').forEach(video => {
        video.addEventListener('click', (e) => {
            e.stopPropagation();
            showVideoModal(video);
        });
    });
    
    // Add click handlers for answer text
    document.querySelectorAll('.answer-item').forEach(answer => {
        answer.addEventListener('click', (e) => {
            // Only show text modal if the click wasn't on an image
            if (!e.target.closest('.answer-image') && !e.target.closest('.answer-video')) {
                showAnswerModal(answer);
            }
        });
    });

    // Add click handler for answer bank
    const answerBank = document.querySelector('.answer-bank');
    if (answerBank) {
        answerBank.addEventListener('click', () => {
            showAnswerBankModal(answerBank);
        });
    }

});