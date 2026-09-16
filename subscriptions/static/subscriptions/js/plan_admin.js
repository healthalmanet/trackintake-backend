document.addEventListener('DOMContentLoaded', function () {
    const planTypeSelect = document.getElementById('id_plan_type');
    if (!planTypeSelect) return;

    function updateFieldsetsVisibility() {
        const selectedType = planTypeSelect.value;
        const patientFieldsets = document.querySelectorAll('.patient-features-group, .patient-limits-group');
        const nutritionistFieldsets = document.querySelectorAll('.nutritionist-features-group, .nutritionist-limits-group');

        if (selectedType === 'nutritionist') {
            patientFieldsets.forEach(el => {
                el.style.display = 'none';
            });
            nutritionistFieldsets.forEach(el => {
                el.style.display = 'block';
            });
        } else {
            // Default or patient
            patientFieldsets.forEach(el => {
                el.style.display = 'block';
            });
            nutritionistFieldsets.forEach(el => {
                el.style.display = 'none';
            });
        }
    }

    planTypeSelect.addEventListener('change', updateFieldsetsVisibility);
    // Initial run
    updateFieldsetsVisibility();
});
