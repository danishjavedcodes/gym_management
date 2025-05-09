// Form validation
function validateForm() {
    const requiredFields = document.querySelectorAll('input[required], select[required], textarea[required]');
    
    // Check for empty required fields
    for (let field of requiredFields) {
        if (!field.value.trim()) {
            alert(`Please fill in the ${field.name} field`);
            field.focus();
            return false;
        }
    }

    // Validate phone numbers
    const phoneFields = ['phone', 'next_of_kin_phone'];
    for (let fieldName of phoneFields) {
        const field = document.querySelector(`[name="${fieldName}"]`);
        if (field && !validatePhone(field.value)) {
            alert(`Please enter a valid phone number for ${fieldName.replace('_', ' ')}`);
            field.focus();
            return false;
        }
    }

    // Validate age
    const ageField = document.querySelector('[name="age"]');
    if (ageField) {
        const age = parseInt(ageField.value);
        if (isNaN(age) || age < 12 || age > 100) {
            alert('Age must be between 12 and 100');
            ageField.focus();
            return false;
        }
    }

    // Validate height and weight
    const heightField = document.querySelector('[name="height"]');
    const weightField = document.querySelector('[name="weight"]');
    
    if (heightField) {
        const height = parseFloat(heightField.value);
        if (isNaN(height) || height <= 0) {
            alert('Please enter a valid height');
            heightField.focus();
            return false;
        }
    }
    
    if (weightField) {
        const weight = parseFloat(weightField.value);
        if (isNaN(weight) || weight <= 0) {
            alert('Please enter a valid weight');
            weightField.focus();
            return false;
        }
    }

    return true;
}

function validatePhone(phone) {
    // Basic phone validation - allows for various formats
    const phoneRegex = /^[+]?[(]?[0-9]{3}[)]?[-\s.]?[0-9]{3}[-\s.]?[0-9]{4,6}$/;
    return phoneRegex.test(phone.trim());
}

// Add event listeners when document is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Handle form submissions
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!validateForm()) {
                e.preventDefault();
            }
        });
    });

    // Add responsive table wrapper
    const tables = document.querySelectorAll('table');
    tables.forEach(table => {
        const wrapper = document.createElement('div');
        wrapper.className = 'table-responsive';
        table.parentNode.insertBefore(wrapper, table);
        wrapper.appendChild(table);
    });
});