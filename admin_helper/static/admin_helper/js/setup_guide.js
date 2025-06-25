document.addEventListener("DOMContentLoaded", function () {
    const guideCard = document.createElement("div");
    guideCard.id = "setup-guide-card";
  
    guideCard.innerHTML = `
      <button class="toggle-button" id="toggle-guide">Hide</button>
      <div id="setup-guide-content">
        <h4>🛠 Setup Guide</h4>
        <ul>
          <li><strong>Users:</strong> Create department head users and profiles</li>
          <li><strong>Departments:</strong> Create departments and assign heads</li>
          <li><strong>Salaries:</strong> Add SG and Step instances</li>
          <li><strong>Plantillas:</strong> Define and assign to profiles</li>
          <li><strong>Leave Mgt:</strong> Defaults to 1.25 accrued monthly</li>
          <li><strong>Home:</strong>
            <ul>
              <li>Add Announcements</li>
              <li>Add Department Contacts</li>
              <li>Upload Forms</li>
              <li>Add Org Personnel</li>
            </ul>
          </li>
        </ul>
      </div>
    `;
  
    document.body.appendChild(guideCard);
  
    const toggleBtn = document.getElementById("toggle-guide");
    const content = document.getElementById("setup-guide-content");
  
    toggleBtn.addEventListener("click", function () {
      content.classList.toggle("collapsed");
      toggleBtn.textContent = content.classList.contains("collapsed") ? "Show" : "Hide";
    });
  });
  