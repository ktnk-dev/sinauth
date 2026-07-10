/**
 * Runtime config injected into index.html by GET /authorize/web/{web_token}.
 *
 * @typedef {Object} SinauthWebAuthConfig
 * @property {string} serviceName Human-readable name of this authorization server.
 * @property {string} service Service identifier requested by the integrating app.
 * @property {string} onSuccessRedirect Absolute URL where the browser is redirected after login or registration.
 * @property {string|null} onErrorRedirect Absolute URL where the browser is redirected after an error.
 * @property {boolean} registrationEnabled Whether the registration UI should be available.
 */

/** @type {SinauthWebAuthConfig} */
const config = window.SINAUTH_WEB_AUTH

const components = {
  PersonIcon: `<svg xmlns="http://www.w3.org/2000/svg" height="24px" viewBox="0 -960 960 960" width="24px" fill="#e3e3e3"><path d="M367-527q-47-47-47-113t47-113q47-47 113-47t113 47q47 47 47 113t-47 113q-47 47-113 47t-113-47ZM160-240v-32q0-34 17.5-62.5T224-378q62-31 126-46.5T480-440q66 0 130 15.5T736-378q29 15 46.5 43.5T800-272v32q0 33-23.5 56.5T720-160H240q-33 0-56.5-23.5T160-240Z"/></svg>`,
  CloseIcon: `<svg xmlns="http://www.w3.org/2000/svg" height="24px" viewBox="0 -960 960 960" width="24px" fill="#e3e3e3"><path d="M480-424 284-228q-11 11-28 11t-28-11q-11-11-11-28t11-28l196-196-196-196q-11-11-11-28t11-28q11-11 28-11t28 11l196 196 196-196q11-11 28-11t28 11q11 11 11 28t-11 28L536-480l196 196q11 11 11 28t-11 28q-11 11-28 11t-28-11L480-424Z"/></svg>`,
  SavedAccount: data => $.div(
    {class: 'account', id: `user${data.id}`, onclick: () => app.login(data.id)},
    $.div(
      {class: 'image', style: {backgroundImage: data.profile_picture_url ? `url(${data.profile_picture_url})` : '#666', backgroundColor: data.profile_picture_url ? `url(${data.profile_picture_url})` : '#666'}},
      !data.profile_picture_url ? components.PersonIcon : null
    ),
    $.div(
      {class: 'username'},
      data.display_name ? data.display_name : '@' + data.username
    ),
    $.div(
      {class: 'delete', onclick: () => {
        if (app.loginning) return
        if (!confirm('Вы уверены, что хотите скрыть этот аккаунт?')) return
        delete app.saved[data.id]
        app.saved_users_view()
      }},
      components.CloseIcon
    )
  ),
  ButtonWithLoader: (props, text, icon) => {
    const class_ = `loading-${Date.now()}`
    const old_onclick = props.onclick
    props.class += ` ${class_}`
    return {element: $.button(
      props,
      text,
      icon
    ), change:() => select(`.${class_}`).overwrite(
      text,$.div({id: 'loading', class: class_, style: '--size: 15px; border-color: #000'})
    )}},
  NextIcon: `<svg xmlns="http://www.w3.org/2000/svg" height="24px" viewBox="0 -960 960 960" width="24px" fill="#e3e3e3"><path d="M647-440H200q-17 0-28.5-11.5T160-480q0-17 11.5-28.5T200-520h447L451-716q-12-12-11.5-28t12.5-28q12-11 28-11.5t28 11.5l264 264q6 6 8.5 13t2.5 15q0 8-2.5 15t-8.5 13L508-188q-11 11-27.5 11T452-188q-12-12-12-28.5t12-28.5l195-195Z"/></svg>`,

}

const capitalize = (str) => {
  if (!str) return str
  return str.charAt(0).toUpperCase() + str.slice(1)
};

const api = async (path, options = {}) => {
  const response = await fetch(path, {
    ...options,
    headers: {'content-type': 'application/json', ...(options.headers || {})}
  })
  const text = await response.text()
  let body = null
  try {
    body = text ? JSON.parse(text) : null
  } catch (_error) {
    body = text
  }
  return {response, body}
}

const redirectWithParams = (url, params) => {
  const target = new URL(url)
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null) target.searchParams.set(key, String(value))
  })
  window.location.replace(target.toString())
}

const app = {
  loginning: false,
  // saved: {'testuser': testuser},
  saved: JSON.parse(localStorage.getItem('saved_accounts') || '{}'),
  start: () => {
    Main.overwrite(
      $.section(
        {id: 'data'},
        $.div(
          {class: 'auth_info'},
          components.PersonIcon,
          $.h1(capitalize(config.serviceName))
        ),
        $.p(
          {class: 'service_info'},
          `Вы авторизируетесь в сервис`, $.br(), $.span(config.service)
        ),
        $.p(
          {class: 'service_info'},
          `Сервис может использовать логин, публичное имя, аватарку, а также личный идентификатор и информацию об устройстве`
        ),
        config.registrationEnabled ? null : $.p(
          {class: 'service_info'},
          `Регистрация новых аккаунтов отключена`
        )
        
      ),
      $.section(
        {id: 'login'}
      )
    )
    Object.keys(app.saved).length === 0 
    ? app.login_view()
    : app.saved_users_view()
  },

  saved_users_view: () => {
    select('#login').overwrite(
      $.h1('Выберите аккаунт'),
      $.div(
        {class: 'saved_accounts'},
        ...Object.keys(app.saved).map(key => app.saved[key] ? components.SavedAccount(app.saved[key]) : null)
      ),
      $.div(
        {class: 'bottom'},
        $.button(
          {class: 'primary', onclick: () => app.login_view()},
          'Добавить новый аккаунт'
        )
      )
    )
  },
  login_view: (notice = false) => {
    const next = components.ButtonWithLoader(
      {class: 'primary', onclick: () => {
        if (app.loginning) return
        if (!select('#user_login').element.value || !select('#user_password').element.value) return alert('Заполните все поля')
          next.change()
        app.login()
      }},
      'Продолжить',
      components.NextIcon
    )

    if (app.loginning) return 
    select('#login').overwrite(
      $.h1('Войдите в аккаунт'),
      $.div(
        {class: 'login_form'},
        $.input({id: 'user_login', placeholder: 'Логин'}),
        $.input({id: 'user_password', type: 'password', placeholder: 'Пароль'})
      ),
      (config.registrationEnabled || notice)? $.p(!notice ? 'Если у аккаунта нет, то он будет создан автоматически' : notice) : null,
      $.div(
        {class: 'bottom'},
        Object.keys(app.saved).length > 0 ? $.button(
          {class: '', onclick: () => app.loginning ? null : app.saved_users_view()},
          'Назад'
        ) : null,
        next.element
      )
    )
  },
  register_view: (login, password) => {
    const next = components.ButtonWithLoader(
      {class: 'primary', onclick: () => {
        if (app.loginning) return
        next.change()
        app.register(login, password)
        
      }},
      'Зарегистрироваться',
      components.NextIcon
    )

    if (app.loginning) return 
    select('#login').overwrite(
      $.h1('Регистрация'),
      $.div(
        {class: 'login_form'},
        $.input({id: 'user_public_name', placeholder: 'Общедоступное имя'}),
        $.input({id: 'user_profile_picture_url', placeholder: 'URL аватара'}),  
      ),
      $.p('Эти поля рекомендуется заполнить, но они не обязательны для регистрации'),
      $.div(
        {class: 'bottom'},
        $.button(
          {class: '', onclick: () => app.loginning ? null : app.login_view()},
          'Назад'
        ),
        next.element
      )
    )
  },
  save: (user, password) => {
    app.saved[user.id] = {
      id: user.id,
      username: user.username,
      password: password,
      display_name: user.display_name,
      profile_picture_url: user.profile_picture_url
    }
    localStorage.setItem('saved_users', JSON.stringify(app.saved))
  },
  login: async (userid = false) => {
    if (app.loginning) return
    if (userid && !app.saved[userid]) return
    const data = userid ? {
      login: app.saved[userid].username,
      password: app.saved[userid].password,
      service: config.service
    } : {
      login: select('#user_login').element.value,
      password: select('#user_password').element.value,
      service: config.service
    }
    if (data.login.length === 0 || data.password.length === 0) {
      return alert('Не все поля заполнены')
    }
    app.loginning = true
    if (userid) select(`#user${userid} > .delete`).overwrite($.div({id: 'loading', style: '--size: 15px'}))
    
    // handle if account exist, if not: call app.regiser_view(login, password) if registation allowed, if not - show an alert and return
    const exists = await api(`/authorize/api/users/exists/${encodeURIComponent(data.login)}`)
    if (!exists.response.ok) {
      app.loginning = false
      app.login_view()
      return alert('Не удалось проверить аккаунт')
    }
    if (!exists.body.exists) {
      app.loginning = false
      if (config.registrationEnabled) {
        return app.register_view(data.login, data.password)
      }
      app.login_view()
      return alert('Аккаунт не найден, регистрация новых аккаунтов отключена')
    }

    // handle login here if account exits
    const auth = await api('/authorize/api/login', {
      method: 'POST',
      body: JSON.stringify({
        username: data.login,
        password: data.password,
        service: data.service
      })
    })
    
    // if login fails: use this
    if (!auth.response.ok) {
      app.loginning = false
      if (userid) {
        return app.login_view("Не удалось войти в аккаунт, возможно пароль был изменен")
      } else {
        return app.login_view("Неправильный логин или пароль")
      }
    }


    // handle getting /me on authorized token to save its data in storage for fast login
    const me = await api('/me', {
      headers: {authorization: `Bearer ${auth.body.access_token}`}
    })
    if (me.response.ok) {
      app.save(me.body, data.password)
    }
    app.loginning = false


    // handle redirect here
    redirectWithParams(config.onSuccessRedirect, {
      access_token: auth.body.access_token,
      token_type: auth.body.token_type,
      expires_at: auth.body.expires_at,
      username: data.login,
      service: config.service
    })
  },
  register: async (login, password) => {
    app.loginning = true
    
    const publicName = select('#user_public_name').element.value;
    const profilePictureUrl = select('#user_profile_picture_url').element.value;
    
    // handle registration here
    const payload = {
      login,
      password,
      display_name: publicName || login,
      service: config.service
    }
    if (profilePictureUrl) payload.profile_picture_url = profilePictureUrl

    const registration = await api('/authorize/api/register', {
      method: 'POST',
      body: JSON.stringify(payload)
    })

    if (!registration.response.ok) {
      app.loginning = false
      if (registration.response.status === 409) return app.login_view('Такой аккаунт уже существует, попробуйте войти')
      if (registration.response.status === 403) return app.login_view('Регистрация новых аккаунтов отключена')
      return app.login_view(registration.body.detail || 'Не удалось зарегистрироваться')
    }

    const me = await api('/me', {
      headers: {authorization: `Bearer ${registration.body.access_token}`}
    })
    if (me.response.ok) {
      app.save(me.body, password)
    }

    app.loginning = false
    app.login_view('Вы успешно зарегистрировались, введите заново пароль чтобы войти в аккаунт')
    select('#user_login').element.value = login


  }

}
console.log(config)


void (function () {
  app.start();
})();

void (function () {
  /**
   * Runtime config injected into index.html by GET /authorize/web/{web_token}.
   *
   * @typedef {Object} SinauthWebAuthConfig
   * @property {string} serviceName Human-readable name of this authorization server.
   * @property {string} service Service identifier requested by the integrating app.
   * @property {string} onSuccessRedirect Absolute URL where the browser is redirected after login or registration.
   * @property {string|null} onErrorRedirect Absolute URL where the browser is redirected after an error.
   * @property {boolean} registrationEnabled Whether the registration UI should be available.
   */

  /** @type {SinauthWebAuthConfig} */
  const config = window.SINAUTH_WEB_AUTH;
  
  
  
  
  const loginForm = document.getElementById("login-form");
  const registerForm = document.getElementById("register-form");
  const loginTab = document.getElementById("login-tab");
  const registerTab = document.getElementById("register-tab");
  const message = document.getElementById("message");
  const serviceName = document.getElementById("service-name");

  document.title = `${config.serviceName} Authorization`;
  serviceName.textContent = `${config.serviceName} for ${config.service}`;

  if (!config.registrationEnabled) {
    registerTab.classList.add("hidden");
  }

  function showForm(kind) {
    const isLogin = kind === "login";
    loginForm.classList.toggle("hidden", !isLogin);
    registerForm.classList.toggle("hidden", isLogin);
    loginTab.classList.toggle("active", isLogin);
    registerTab.classList.toggle("active", !isLogin);
    message.textContent = "";
  }

  function formData(form) {
    return Object.fromEntries(new FormData(form).entries());
  }

  function redirectWithParams(baseUrl, params) {
    const url = new URL(baseUrl);
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, String(value));
      }
    }
    window.location.href = url.toString();
  }

  function handleError(body) {
    const detail = body.detail || "Authorization failed";
    if (config.onErrorRedirect) {
      redirectWithParams(config.onErrorRedirect, {
        error: body.error || "authorization_failed",
        error_description: detail,
      });
      return;
    }
    message.textContent = detail;
  }

  async function submit(path, payload, username, submitter) {
    message.textContent = "";
    submitter.disabled = true;
    try {
      const response = await fetch(path, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = await response.json();
      if (response.ok) {
        redirectWithParams(config.onSuccessRedirect, {
          access_token: body.access_token,
          token_type: body.token_type,
          expires_at: body.expires_at,
          username,
          service: config.service,
        });
        return;
      }
      handleError(body);
    } catch (_error) {
      handleError({ detail: "Authorization failed" });
    } finally {
      submitter.disabled = false;
    }
  }

  loginTab.addEventListener("click", () => showForm("login"));
  registerTab.addEventListener("click", () => showForm("register"));

  loginForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const data = formData(loginForm);
    submit(
      "/authorize/api/login",
      {
        username: data.username,
        password: data.password,
        service: config.service,
      },
      data.username,
      event.submitter,
    );
  });

  registerForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const data = formData(registerForm);
    if (!data.profile_picture_url) {
      delete data.profile_picture_url;
    }
    submit(
      "/authorize/api/register",
      {
        ...data,
        service: config.service,
      },
      data.login,
      event.submitter,
    );
  });
})();
