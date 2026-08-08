const form = document.querySelector("#config-form");
const saveButton = document.querySelector("#save-button");
const feedback = document.querySelector("#feedback");
let schemaVersion = 2;

function showFeedback(message, isError = false) {
  feedback.textContent = message;
  feedback.classList.toggle("error", isError);
  feedback.hidden = false;
}

function clearErrors() {
  document.querySelectorAll(".field-error").forEach((item) => { item.textContent = ""; });
  feedback.hidden = true;
}

function populate(config) {
  schemaVersion = Math.max(Number(config.schema_version) || 2, 2);
  form.cli_prefix.value = config.cli_prefix;
  form.scheduled_query_enabled.checked = config.scheduled_query_enabled;
  form.target_group_ids.value = (config.target_group_ids || []).join("\n");
  form.log_group_message_content.checked = config.log_group_message_content;
  form.query_interval_seconds.value = config.query_interval_seconds;
  form.initial_query_count.value = config.initial_query_count;
}

async function loadConfig() {
  try {
    const response = await fetch("/api/config", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    populate(data.config);
    document.querySelector("#version").textContent = `版本 ${data.version}`;
    document.querySelector("#health-dot").classList.add("ok");
    document.querySelector("#health-text").textContent = "服务运行中";
    if (data.load_error) {
      const box = document.querySelector("#load-error");
      box.textContent = data.load_error;
      box.hidden = false;
    }
  } catch (error) {
    document.querySelector("#health-text").textContent = "连接失败";
    showFeedback(`无法读取配置：${error.message}`, true);
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearErrors();
  saveButton.disabled = true;
  const payload = {
    schema_version: schemaVersion,
    cli_prefix: form.cli_prefix.value,
    scheduled_query_enabled: form.scheduled_query_enabled.checked,
    target_group_ids: form.target_group_ids.value
      .split(/\r?\n/)
      .map((value) => value.trim())
      .filter(Boolean),
    log_group_message_content: form.log_group_message_content.checked,
    query_interval_seconds: Number(form.query_interval_seconds.value),
    initial_query_count: Number(form.initial_query_count.value),
  };
  try {
    const response = await fetch("/api/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      Object.entries(data.fields || {}).forEach(([field, message]) => {
        const target = document.getElementById(`${field}-error`);
        if (target) target.textContent = message;
      });
      throw new Error(data.error || "保存失败");
    }
    populate(data.config);
    showFeedback(data.message || "配置已保存并生效");
  } catch (error) {
    showFeedback(error.message, true);
  } finally {
    saveButton.disabled = false;
  }
});

loadConfig();
