document.addEventListener('DOMContentLoaded', function () {
  const profileShell = document.getElementById('profileShell');

      const teacherCatalog = JSON.parse(profileShell?.dataset.teacherCatalog || "[]");
      const orgSelect = document.getElementById('organizationSelect');
      const teacherSelect = document.getElementById('teacherSelect');
      const instituteLabel = document.getElementById('selectedInstituteLabel');
      const teacherLabel = document.getElementById('selectedTeacherLabel');
      const adminLabel = document.getElementById('selectedAdminLabel');

      function renderTeacherOptions() {
        const orgId = parseInt(orgSelect.value || '0', 10);
        const currentTeacher = parseInt(teacherSelect.dataset.selected || teacherSelect.value || '0', 10);
        const options = teacherCatalog.filter(item => item.id === 0 || item.organization_id === orgId || (!orgId && item.organization_id === 0));
        teacherSelect.innerHTML = '';
        options.forEach(item => {
          const opt = document.createElement('option');
          opt.value = item.id;
          opt.textContent = item.label;
          if (item.id === currentTeacher) {
            opt.selected = true;
          }
          teacherSelect.appendChild(opt);
        });
        if (!teacherSelect.value) {
          teacherSelect.value = '0';
        }
      }

      function updatePreview() {
        const orgText = orgSelect.options[orgSelect.selectedIndex] ? orgSelect.options[orgSelect.selectedIndex].text : 'Independent Learner';
        const teacherText = teacherSelect.options[teacherSelect.selectedIndex] ? teacherSelect.options[teacherSelect.selectedIndex].text : 'Not assigned yet';
        instituteLabel.textContent = orgText || 'Independent Learner';
        teacherLabel.textContent = teacherText || 'Not assigned yet';
        adminLabel.textContent = parseInt(orgSelect.value || '0', 10) ? orgText : 'Fluencify Support Team';
      }

      teacherSelect.dataset.selected = teacherSelect.value || '0';
      renderTeacherOptions();
      updatePreview();

      orgSelect.addEventListener('change', function () {
        teacherSelect.dataset.selected = '0';
        renderTeacherOptions();
        updatePreview();
      });
      teacherSelect.addEventListener('change', updatePreview);
    
});
