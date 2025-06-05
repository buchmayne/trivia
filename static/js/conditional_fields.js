document.addEventListener('DOMContentLoaded', function() {
    // Function to show/hide correct_rank fields based on question type
    function toggleCorrectRankFields() {
        const questionTypeSelect = document.getElementById('id_question_type');
        if (!questionTypeSelect) return;
        
        const isRankingType = questionTypeSelect.options[questionTypeSelect.selectedIndex].text === 'Ranking';
        
        // Get all table headers and cells for correct_rank
        const correctRankHeaders = document.querySelectorAll('th.column-correct_rank');
        const correctRankCells = document.querySelectorAll('td.field-correct_rank');
        
        // Hide/show the header
        correctRankHeaders.forEach(header => {
            header.style.display = isRankingType ? '' : 'none';
        });
        
        // Hide/show each cell
        correctRankCells.forEach(cell => {
            cell.style.display = isRankingType ? '' : 'none';
        });
    }
    
    // Initial setup when page loads
    toggleCorrectRankFields();
    
    // Add event listener for question type change
    const questionTypeSelect = document.getElementById('id_question_type');
    if (questionTypeSelect) {
        questionTypeSelect.addEventListener('change', toggleCorrectRankFields);
    }
    
    // Handle dynamically added inline forms (when "Add another Answer" is clicked)
    const addButtons = document.querySelectorAll('.add-row a');
    addButtons.forEach(button => {
        button.addEventListener('click', function() {
            // Use setTimeout to wait for the DOM to update
            setTimeout(toggleCorrectRankFields, 100);
        });
    });
    
    // Also handle when the inline formset is updated via Django's dynamic inlines
    django.jQuery(document).on('formset:added', function() {
        toggleCorrectRankFields();
    });
});