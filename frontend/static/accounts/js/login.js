const passwordToggle = document.querySelector(".password-toggle");
const passwordInput = document.querySelector("#id_password");

if (passwordToggle && passwordInput) {
    passwordToggle.addEventListener("click", () => {
        const isVisible = passwordInput.type === "text";
        passwordInput.type = isVisible ? "password" : "text";
        passwordToggle.setAttribute("aria-pressed", String(!isVisible));
        passwordToggle.setAttribute("aria-label", isVisible ? "Show password" : "Hide password");
    });
}
