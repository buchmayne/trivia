document.addEventListener('DOMContentLoaded', function() {
    const categorySelect = document.getElementById('id_category');
    if (!categorySelect) return;

    // Define defaults for specific categories
    const categoryDefaults = {
        // Replace these IDs with your actual category IDs
        "15": { // "Guess the Data" category ID
            "text": "Identify the data being shown on the map (5 Points).",
            "total_points": 5,
            "game_round": 2,
            "question_type": "Multiple Open Ended",
            "answer_bank": ""
        },
        "19": { // "Visual Pun" category ID
            "text": "The following four image collage is a visual pun.\n<br><br> Guess what each image represents for 3 Points, and then what the category is that connects them for an additional 3 Points (15 Points Total).",
            "total_points": 15,
            "game_round": 2,
            "question_type": "Multiple Open Ended",
            "answer_bank": ""
        },
        "18": { // "Bird's Eye View" category ID
            "text": "Identify the famous INTERNATIONAL/NATIONAL place from the satellite photo (5 Points).",
            "total_points": 5,
            "game_round": 2,
            "question_type": "Multiple Open Ended",
            "answer_bank": ""
        },
        "13": { // "Six Degrees of Separation" category ID
            "text": "Connect the actors by films they share a collaborator with. Connect ACTOR_1 to ACTOR_2 in as few degrees as possible. Scoring: 6 Degrees: 1 Point, +2 Points for each fewer degree.",
            "total_points": 11,
            "game_round": 2,
            "question_type": "Multiple Open Ended",
            "answer_bank": "Example, connect Jack Nicholson to The Rock. This is a possible answer, that is 2 degrees of separation as each movie is a degree: 1. Jack Nicholson (The Departed) Mark Wahlberg 2. Mark Wahlberg (The Other Guys) The Rock"
        },
    };

    // Function to update form fields based on selected category
    const updateFieldsForCategory = (categoryId) => {
        const defaults = categoryDefaults[categoryId];
        if (!defaults) return;

        // Only update fields if they're empty or if this is a new form
        const questionTextField = document.getElementById('id_text');
        const totalPointsField = document.getElementById('id_total_points');
        const gameRoundField = document.getElementById('id_game_round');
        const questionTypeField = document.getElementById('id_question_type');
        const answerBankField = document.getElementById('id_answer_bank');


        // Check if this is likely a new form (text field is empty)
        const isNewForm = questionTextField && !questionTextField.value.trim();
        
        if (isNewForm) {
            // Update the fields with defaults
            if (questionTextField && defaults.text) {
                questionTextField.value = defaults.text;
            }
            
            if (totalPointsField && defaults.total_points) {
                totalPointsField.value = defaults.total_points;
            }
            
            if (gameRoundField && defaults.game_round) {
                gameRoundField.value = defaults.game_round;
            }

            if (questionTypeField && defaults.question_type) {
                questionTypeField.value = defaults.question_type;
            }

            if (answerBankField && defaults.answer_bank) {
                answerBankField.value = defaults.answer_bank;
            }
        }
    };

    // Add event listener to the category select
    categorySelect.addEventListener('change', function() {
        updateFieldsForCategory(this.value);
    });

    // Also check on page load in case a category is pre-selected
    if (categorySelect.value) {
        updateFieldsForCategory(categorySelect.value);
    }
});