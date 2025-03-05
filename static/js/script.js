// Form validation
function validateForm() {
    const requiredFields = document.querySelectorAll('input[required]');
    for (let field of requiredFields) {
        if (!field.value) {
            alert('Please fill in all required fields');
            return false;
        }
    }
    return true;
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