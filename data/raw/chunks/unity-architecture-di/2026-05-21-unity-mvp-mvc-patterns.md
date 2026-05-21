---
title: Unity 6 — MVC·MVP Programming Patterns (Unity Learn)
slug: 2026-05-21-unity-mvp-mvc-patterns
created_at: '2026-05-21T10:39:49+09:00'
status: draft
source_type: url
lang: ko
tags:
- mvc
- mvp
- design-patterns
- unity
source_url: https://learn.unity.com/course/design-patterns-unity-6/tutorial/build-a-modular-codebase-with-mvc-and-mvp-programming-patterns
fetched_at: '2026-05-21T10:39:49+09:00'
summary: MVC와 MVP 패턴은 데이터(Model)·표현(View)·제어(Controller/Presenter)를 분리해 Unity 프로젝트의
  코드 유지보수성과 확장성을 높이는 수단이다. Unity의 UI 시스템이 이미 View 역할을 수행하므로 많은 개발자는 Presenter를 중개자로
  두는 MVP 변형을 채택하며, 예시에서 Health는 값과 HealthChanged 이벤트만 보유하고 HealthPresenter가 Damage/Heal/Reset
  호출과 UI 갱신을 담당해 책임이 명확히 분리된다. 다만 패턴은 그대로 복사해 쓰는 완성된 해법이 아니라 상황에 맞게 적용해야 하는 도구이며,
  본문이 중간에 잘려 있어 전체 구현 세부는 확인되지 않는다.
---
## TL;DR
MVC와 MVP 패턴은 데이터(Model)·표현(View)·제어(Controller/Presenter)를 분리해 Unity 프로젝트의 코드 유지보수성과 확장성을 높이는 수단이다. Unity의 UI 시스템이 이미 View 역할을 수행하므로 많은 개발자는 Presenter를 중개자로 두는 MVP 변형을 채택하며, 예시에서 Health는 값과 HealthChanged 이벤트만 보유하고 HealthPresenter가 Damage/Heal/Reset 호출과 UI 갱신을 담당해 책임이 명확히 분리된다. 다만 패턴은 그대로 복사해 쓰는 완성된 해법이 아니라 상황에 맞게 적용해야 하는 도구이며, 본문이 중간에 잘려 있어 전체 구현 세부는 확인되지 않는다.

Title: Build a modular codebase with MVC and MVP programming patterns  - Unity Learn

URL Source: https://learn.unity.com/course/design-patterns-unity-6/tutorial/build-a-modular-codebase-with-mvc-and-mvp-programming-patterns

Markdown Content:
By implementing common game programming design patterns in your Unity project, you can efficiently build and maintain a clean, organized, and readable codebase. Design patterns not only reduce refactoring and time spent testing, but they also speed up onboarding and development processes, contributing to a solid foundation that can be used to grow your game, development team, and business.

Think of design patterns not as finished solutions you can copy and paste into your code, but as extra tools that, when used correctly, can help you build larger, scalable applications.

This tutorial explains how you can efficiently build and maintain a clean, organized, and readable codebase by implementing MVC and MVP design patterns in your Unity project.

## 1. Level up your code: Model-view-presenter

Before you begin this tutorial, check out the video below for a brief overview of how you can use the Model-view-presenter design pattern in your Unity projects. This pattern can help neatly organize your code so it’s easier to manage, less error-prone and more flexible for future updates.

[Video 3](https://www.youtube.com/watch?v=agoe5BdLzdk)

![Image 1](https://img.youtube.com/vi/agoe5BdLzdk/maxresdefault.jpg)

Video Player is loading.

Current Time 0:00

Duration 7:09

Loaded: 0.00%

Remaining Time 7:09

## 2. Overview

By implementing common game programming design patterns in your Unity project, you can efficiently build and maintain a clean, organized, and readable codebase. Design patterns not only reduce refactoring and time spent testing, but they also speed up onboarding and development processes, contributing to a solid foundation that can be used to grow your game, development team, and business.

Think of design patterns not as finished solutions you can copy and paste into your code, but as extra tools that, when used correctly, can help you build larger, scalable applications.

This tutorial explains how you can efficiently build and maintain a clean, organized, and readable codebase by implementing MVC and MVP design patterns in your Unity project.

The content here is based on the free e-book, [Level up your code with design patterns and SOLID](https://unity.com/resources/design-patterns-solid-ebook?isGated=false&ampDeviceId=24cf503c-7219-4ae1-a2d6-27994ea5f391&ampSessionId=1779327551507&ampTimestamp=1779413951515), , which explains well known design patterns and shares practical examples for using them in your Unity project.

Other articles in the Unity game programming patterns series are available on the [Unity best practices](https://unity.com/how-to?ampDeviceId=24cf503c-7219-4ae1-a2d6-27994ea5f391&ampSessionId=1779327551507&ampTimestamp=1779413951515) hub, or you can check out the following links:

## 3. Benefits of using design patterns

You can use the Model View Controller (MVC) and Model View Presenter (MVP) design patterns to separate the data and logic in your application from how it’s being presented. These patterns apply the principles of separation of concerns, which can improve the flexibility and maintainability of your codebase.

In Unity game development, you can use these patterns to separate the logic of a game into distinct components, like the data (Model), the visual representation (View), and the logic that controls the interaction between the two (Controller or Presenter).

## 4. The MVC design pattern

MVC is a family of design patterns commonly used when developing user interfaces in software applications.

The general idea behind MVC is to separate the logical portion of your software from the data and the presentation. This helps reduce unnecessary dependencies and can potentially cut down on [spaghetti code](https://en.wikipedia.org/wiki/Spaghetti_code).

As the name implies, the MVC pattern splits your application into three layers:

*   **The Model stores data:** The Model is strictly a data container that holds values. It does not perform gameplay logic or run calculations.
*   **The View is the interface:** The View formats and renders a graphical presentation of your data onscreen.
*   **The Controller handles logic**: Think of this as the brain. It processes the game data and calculates how the values change at runtime.

This separation of concerns also specifically defines how these three parts interact with one another. The Model manages the application data, while the View displays that data to the user. The Controller handles input and performs any decisions or calculations on the game data.

Then it sends the results back to the Model.

The Controller does not contain any game data unto itself. Nor does the View. The MVC design limits what each layer does. One part holds the data, another part processes the data, and the last one displays that data to the user.

On the surface, you can think of this as an extension of the single-responsibility principle. Each part does one thing and does it well, which is the key advantage of MVC architecture.

## 5. MVP and Unity

A [sample project](https://assetstore.unity.com/packages/essentials/tutorial-projects/level-up-your-code-with-design-patterns-and-solid-289616?ampDeviceId=24cf503c-7219-4ae1-a2d6-27994ea5f391&ampSessionId=1779327551507&ampTimestamp=1779413951515) is available on the Unity Asset Store that demonstrates different programming design patterns, including an example of how to implement a variation of the MVP.

When developing a Unity project with MVC, the existing UI framework (either the [UI Toolkit](https://docs.unity3d.com/Manual/UIElements.html?ampDeviceId=24cf503c-7219-4ae1-a2d6-27994ea5f391&ampSessionId=1779327551507&ampTimestamp=1779413951515) or [Unity UI](https://docs.unity3d.com/Manual/com.unity.ugui.html?ampDeviceId=24cf503c-7219-4ae1-a2d6-27994ea5f391&ampSessionId=1779327551507&ampTimestamp=1779413951515)) naturally functions as the View. Because the engine gives you a complete user interface implementation, you won’t need to develop individual UI components from scratch.

However, following the traditional MVC pattern would require View-specific code to listen for any changes in the Model’s data at runtime.

While this is a valid approach, many Unity developers opt to use a variation on MVC where the Controller acts as an intermediary. Here, the View doesn’t directly observe the Model. Instead, it does something like in the diagram above.

This variation on MVC is called the Model View Presenter design, or MVP. MVP still preserves the separation of concerns with three distinct application layers. However, it slightly changes each part’s responsibilities.

In MVP, the Presenter (called the Controller in MVC) acts as a go-between for the other layers. It retrieves data from the Model and then formats it for display in the View. MVP switches which layer handles input. Rather than the Controller, the View is responsible for handling user input.

Notice how events and the observer pattern figure into this design. The user can interact with Unity UI’s Button, Toggle, and Slider components. The View layer sends this input back to the Presenter via UI events, and the Presenter, in turn, manipulates the Model. A state-change event from the Model tells the Presenter that the data has been updated. The Presenter passes the modified data to the View, which refreshes the UI.

## 6. Try our sample project

A [sample project](https://assetstore.unity.com/packages/essentials/tutorial-projects/level-up-your-code-with-design-patterns-and-solid-289616?ampDeviceId=24cf503c-7219-4ae1-a2d6-27994ea5f391&ampSessionId=1779327551507&ampTimestamp=1779413951515) is available on the Unity Asset Store that demonstrates different programming design patterns, including an example of how to implement a variation of the MVP.

The MVP example consists of a simple system that shows the health of a character or item. This example has everything in one class that mixes the data and UI, but that wouldn’t scale well in real-world productions. Adding more functionality would become more complicated as you need to expand it. In addition, testing and refactoring would result in a lot of overhead.

Instead, you can rewrite your health components in a more MVP-centric way, starting by dividing your scripts into a Health and HealthPresenter.

In the [sample project](https://assetstore.unity.com/packages/essentials/tutorial-projects/level-up-your-code-with-design-patterns-and-solid-289616?ampDeviceId=24cf503c-7219-4ae1-a2d6-27994ea5f391&ampSessionId=1779327551507&ampTimestamp=1779413951515), you can click to damage the target object represented by a shooting disc (**ClickDamage.cs**), or reset the health with the button. These events inform the **HealthPresenter**(which invokes **Damage**or **Reset**) rather than change the **Health**directly. The UI Text and UI Slider update when the **Health**raises an event and notifies the **HealthPresenter**that its values have changed.

## 7. The Health interface

Let’s dive deeper into what a **Health**component could look like. In this version, **Health**serves as the Model. It stores the actual health value and invokes an event, **HealthChanged**, every time that value changes. **Health**does not contain gameplay logic, only methods to increment and decrement the data.

This allows a clear distinction between the data, the way it’s presented, and the way it’s controlled.

```
public class Health: MonoBehaviour
{
    public event Action HealthChanged;

    private const int minHealth = 0;
    private const int maxHealth = 100;
    private int currentHealth;

    public int CurrentHealth { get => currentHealth; set => currentHealth = value; }
    public int MinHealth => minHealth;
    public int MaxHealth => maxHealth;

    public void Increment(int amount)
    {
        currentHealth += amount;
        currentHealth = Mathf.Clamp(currentHealth, minHealth, maxHealth);
        UpdateHealth();
    }

    public void Decrement(int amount)
    {
        currentHealth -= amount;
        currentHealth = Mathf.Clamp(currentHealth, minHealth, maxHealth);
        UpdateHealth();
    }

    public void Restore()
    {
        currentHealth = maxHealth;
        UpdateHealth();
    }

    public void UpdateHealth()
    {
        HealthChanged?.Invoke();
    }
}
```

## 8. The HealthPresenter

In the example discussed above, most objects won’t manipulate the **Health**itself. You’ll reserve a **HealthPresenter**for that task.

Other GameObjects will need to use the **HealthPresenter**to modify the health values using **Damage**, **Heal**, and **Reset**. The **HealthPresenter**usually waits to update the user interface with the UpdateView until the Health raises its **HealthChanged**event. This is useful if setting the values in the Model takes a short duration (for example, saving values to disk or storing them in a database).

```
public class HealthPresenter : MonoBehaviour
{
    [SerializeField] Health health;
    [SerializeField] Slider healthSlider;

    private void Start()
    {
        if (health != null)
        {
            health.HealthChanged += OnHealthChanged;
        }
        UpdateView();
    }

    private void OnDestroy()
    {
        if (health != null)
        {
            health.HealthChanged -= OnHealthChanged;
        }
    }

    public void Damage(int amount)
    {
        health?.Decrement(amount);
    }

    public void Heal(int amount)
    {
        health?.Increment(amount);
    }

    public void Reset()
    {
        health?.Restore();
    }

    public void UpdateView()
    {
        if (health == null)
            return;

        if (healthSlider !=null && health.MaxHealth != 0)
        {
            healthSlider.value = (float) health.CurrentHealth / (float)health.MaxHealth;
        }
    }

    public void OnHealthChanged()
    {
        UpdateView();
    }
}
```

## 9. Pros and cons

MVP (and MVC) really shine for larger and UI-heavy software applications, but it’s not limited to those use cases. If your game requires a sizable team to develop and you expect to maintain it for a long time after launch, you might see the following benefits:

*   **Smooth division of work:**Because you’ve separated the View from the Presenter, developing and updating your user interface can happen nearly independently from the rest of the codebase.

This lets you divide your labor between specialized developers. Do you have expert front-end developers on your team? If so, let them take care of the View.

*   **Simplified unit testing with MVP and MVC:** These design patterns separate gameplay logic from the user interface. As such, you can simulate objects to work with your code without actually needing to enter Play mode in the Editor. This can save considerable amounts of time.

*   **Readable code that can be maintained:** You’ll tend to make smaller classes with this design pattern, which makes them easier to read. Fewer dependencies usually means fewer places for your software to break, fewer places that might be hiding bugs, and easier testing.

Though MVC and MVP are widespread in web development or enterprise software, often, the benefits won’t be apparent until your application reaches a sufficient size and complexity. You’ll need to consider the following before implementing either pattern in your Unity project:

*   **You need to plan ahead:** MVC and MVP are larger architectural patterns. To use one of them, you’ll need to split your classes by responsibility, which takes some organization and requires more work up front. Design patterns are best used consistently, so you’ll want to establish a practice for organizing your UI and ensure that your team is onboard.

*   **Not everything in your Unity project will fit the pattern:** In a pure MVC or MVP implementation, anything that renders to screen really is part of the View. Not every Unity component is easily split between data, logic, and interface (for example, a MeshRenderer). Also, simple scripts may not yield many benefits from MVC/MVP.
You’ll need to judge where you can benefit the most from the pattern. Usually, you can let the unit tests guide you. If MVC/MVP can facilitate testing, consider them for that aspect of the application. Otherwise, don’t try to force the pattern onto your project.

Language

Social

"Unity", Unity logos, and other Unity trademarks are trademarks or registered trademarks of Unity Technologies or its affiliates in the U.S. and elsewhere ([more info here](https://unity.com/legal/trademarks?ampDeviceId=24cf503c-7219-4ae1-a2d6-27994ea5f391&ampSessionId=1779327551507&ampTimestamp=1779413951515)). Other names or brands are trademarks of their respective owners.



