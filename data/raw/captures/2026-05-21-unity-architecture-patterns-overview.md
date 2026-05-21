---
title: Unity Game Architecture — Patterns Overview (MVC/MVP/MVVM/ECS)
slug: 2026-05-21-unity-architecture-patterns-overview
created_at: '2026-05-21T10:40:53+09:00'
status: draft
source_type: url
lang: ko
tags:
- unity
- game-architecture
- mvc
- design-patterns
source_url: https://dev.to/devsdaddy/organizing-architecture-for-games-on-unity-laying-out-the-important-things-that-matter-4d4p
fetched_at: '2026-05-21T10:40:53+09:00'
summary: 결론적으로 Unity 게임은 초기 단계부터 아키텍처를 잘 설계해야 확장성·유지보수성·성능·개발 속도를 모두 확보할 수 있다. 근거로
  관심사 분리·모듈성·가독성·단순성 원칙 위에 MVC·MVP·MVVM·ECS 같은 핵심 패턴과 Singleton·Observer·Command 등의
  보조 패턴을 Unity의 컴포넌트 지향 특성에 맞게 적용해 데이터·로직·표현을 분리하는 방식이 제시된다. 다만 본문은 MVC 코드 예시 중간에서
  잘려 있어 나머지 패턴의 구체 구현은 확인할 수 없다.
---
## TL;DR
결론적으로 Unity 게임은 초기 단계부터 아키텍처를 잘 설계해야 확장성·유지보수성·성능·개발 속도를 모두 확보할 수 있다. 근거로 관심사 분리·모듈성·가독성·단순성 원칙 위에 MVC·MVP·MVVM·ECS 같은 핵심 패턴과 Singleton·Observer·Command 등의 보조 패턴을 Unity의 컴포넌트 지향 특성에 맞게 적용해 데이터·로직·표현을 분리하는 방식이 제시된다. 다만 본문은 MVC 코드 예시 중간에서 잘려 있어 나머지 패턴의 구체 구현은 확인할 수 없다.

Title: Organizing architecture for games on Unity: Laying out the important things that matter

URL Source: https://dev.to/devsdaddy/organizing-architecture-for-games-on-unity-laying-out-the-important-things-that-matter-4d4p

Published Time: 2024-04-08T19:57:53Z

Markdown Content:
**Hello everyone.** In the world of game development, effective organization of project architecture plays a key role. **Unity, one of the most popular game engines**, provides developers with a huge set of tools to create a variety of games. However, without the right architecture, a project can quickly become **unmanageable** and **difficult to maintain** and extend.

[![Image 1: Unity Architecture Patterns](https://media2.dev.to/dynamic/image/width=800%2Cheight=%2Cfit=scale-down%2Cgravity=auto%2Cformat=auto/https%3A%2F%2Fdev-to-uploads.s3.amazonaws.com%2Fuploads%2Farticles%2Fc10laxczdmaqowh8w7do.png)](https://media2.dev.to/dynamic/image/width=800%2Cheight=%2Cfit=scale-down%2Cgravity=auto%2Cformat=auto/https%3A%2F%2Fdev-to-uploads.s3.amazonaws.com%2Fuploads%2Farticles%2Fc10laxczdmaqowh8w7do.png)

In this article, we will discuss the importance of organizing the architecture for Unity games and give some modern approaches to its organization.

## [](https://dev.to/devsdaddy/organizing-architecture-for-games-on-unity-laying-out-the-important-things-that-matter-4d4p#the-importance-of-architecture-organization-in-game-development) The importance of architecture organization in game development

The organization of architecture in game development certainly plays one of the decisive roles in the success of a project. **A well-designed architecture provides the following benefits:**

1.   **Scalability**: The right architecture makes the project flexible and easily scalable. This allows you to add new features and modify existing ones without seriously impacting the entire system.

2.   **Maintainability**: Clean and organized code is easier to understand, change, and maintain. This is especially important in game development, where changes can occur frequently.

3.   **Performance**: Efficient architecture helps optimize game performance by managing system resources and ensuring smooth gameplay.

4.   **Speed of development:** A good and usable architecture will speed up the pace of development by reducing cohesion, code duplication, and other aspects

[![Image 2: Good Architecture Aspects](https://media2.dev.to/dynamic/image/width=800%2Cheight=%2Cfit=scale-down%2Cgravity=auto%2Cformat=auto/https%3A%2F%2Fdev-to-uploads.s3.amazonaws.com%2Fuploads%2Farticles%2Fb1881e6zr7ksb1amz18v.png)](https://media2.dev.to/dynamic/image/width=800%2Cheight=%2Cfit=scale-down%2Cgravity=auto%2Cformat=auto/https%3A%2F%2Fdev-to-uploads.s3.amazonaws.com%2Fuploads%2Farticles%2Fb1881e6zr7ksb1amz18v.png)

> And you should think about the architecture of the project at the earliest stages, because in the future it will reduce the number of refactoring and revisions of your project, and it also allows you to properly think about the business processes - how often and quickly you can adapt your project to new requirements.

## [](https://dev.to/devsdaddy/organizing-architecture-for-games-on-unity-laying-out-the-important-things-that-matter-4d4p#basic-principles-of-architecture-in-unity-games) Basic principles of architecture in Unity games

Of course, game development in general is always similar, but different tools and game engines still have different approaches to writing code. Before we start looking at specific approaches to organizing architecture on Unity, **let's discuss a few key principles to keep in mind:**

1.   **Separation of Concerns:** Each component of the project should perform one specific task. This reduces dependencies between components and makes it easier to test and modify them.

2.   **Modularity and Flexibility:** Design the system so that each part is independent and easily replaceable. This allows for flexible and adaptive systems that can adapt to changing project requirements.

3.   **Code Readability and Comprehensibility:** Use clear variable and function names, break code into logical blocks and document it. This makes the code more understandable and makes it easier to work together on the project.

4.   **Don't complicate things where you don't need to:** many people strive to create perfect code, but as we know, nothing is perfect in nature, so in programming - don't complicate things where they can be made simpler and straightforward. It will save you time and money.

> What you still need to understand is that **Unity initially gives a component-oriented approach**, which means that some things that in classical programming are done one way, here will look a little different, which means that some patterns will have to be adapted to the game engine.

**In essence, any patterns serve for basic organization of the concept of writing game code:**

1.   **Create a data model and link it to game objects**: Define the basic data of your game and create the corresponding model classes. Then establish a relationship between this data and the game objects in your project.

2.   **Implement interaction control via controllers**: Create controllers that control the interaction between different components of your game. For example, a controller can control the movement of a character or the processing of player input.

3.   **Use the component system to****display objects:** Use the Unity component system to display the result of controlling game objects. Divide object behavior into individual components and add them to objects as needed.

**Now, having understood a little bit about the basic principles and concepts let's move directly to the design patterns.**

## [](https://dev.to/devsdaddy/organizing-architecture-for-games-on-unity-laying-out-the-important-things-that-matter-4d4p#architecture-patterns-for-games-on-unity)**Architecture Patterns for games on Unity**

**Design patterns** are basic concepts, or in other words, blanks that allow you to simplify the organization of basic things in software development. There are many design patterns that can be applied to organizing game architecture on Unity. **Below we will look at a few of the most popular ones:**

1.   **MVC (Model-View-Controller):** a scheme for separating application data and control logic into three separate components - model, view, and controller - so that modification of each component can be done independently.

2.   **MVP (Model-View-Presenter):** a design pattern derived from MVC that is used primarily for building user interfaces.

3.   **MVVM (Model-View-ViewModel):** a pattern that grew up as an improved version of MVC, which brings the main program logic into Model, displays the result of work in View, and ViewModel works as a layer between them.

4.   **ECS (Entity Component System):** this pattern is closer to the basic component approach in Unity, but may be more difficult to understand for those who have worked primarily with OOP patterns. It also divides the whole game into Entities, Systems and Components.

[![Image 3: Unity Architecture Patterns](https://media2.dev.to/dynamic/image/width=800%2Cheight=%2Cfit=scale-down%2Cgravity=auto%2Cformat=auto/https%3A%2F%2Fdev-to-uploads.s3.amazonaws.com%2Fuploads%2Farticles%2Fqrcs0a1289641v6ynsmt.png)](https://media2.dev.to/dynamic/image/width=800%2Cheight=%2Cfit=scale-down%2Cgravity=auto%2Cformat=auto/https%3A%2F%2Fdev-to-uploads.s3.amazonaws.com%2Fuploads%2Farticles%2Fqrcs0a1289641v6ynsmt.png)

**Also, additional patterns can help you in your design, the implementation and examples of which we will also see in this article for Unity:**

1.   **Singleton:** pattern is widely used in software development. It ensures that only one instance of a class is created and provides a global access point for the resources it provides;

2.   **Target-Action:** The role of a control in a user interface is quite simple: it senses the user's intent to do something and instructs another object to process that request. The Target-Action pattern is used to communicate between the control and the object that can process the request;

3.   **Observer:** this pattern is most often used when it is necessary to notify an "observer" about changes in the properties of our object or about the occurrence of any events in this object. Usually the observer "registers" his interest in the state of another object;

4.   **Command:** is a behavioral design pattern that turns queries into objects, allowing you to pass them as arguments to method calls, queue queries, log them, and support undo operations;

**So, let's get started.**

* * *

### [](https://dev.to/devsdaddy/organizing-architecture-for-games-on-unity-laying-out-the-important-things-that-matter-4d4p#model-view-controller-mvc) Model View Controller (MVC)

> The bigger the project, the bigger the spaghetti.

**MVC was born to solve this problem**. This architectural pattern helps you accomplish this by separating the data, managing it, and presenting its final output to the user.

[![Image 4: Unity Patterns - MVC](https://media2.dev.to/dynamic/image/width=800%2Cheight=%2Cfit=scale-down%2Cgravity=auto%2Cformat=auto/https%3A%2F%2Fucarecdn.com%2Fa7757d38-f373-45af-a01a-2d109a5f4ae7%2F%2520align%3D)](https://media2.dev.to/dynamic/image/width=800%2Cheight=%2Cfit=scale-down%2Cgravity=auto%2Cformat=auto/https%3A%2F%2Fucarecdn.com%2Fa7757d38-f373-45af-a01a-2d109a5f4ae7%2F%2520align%3D)

The gaming and UI development will have the usual workflow of waiting for input. Only when they receive an input of any form they can decide upon the appropriate response, and update the data accordingly. These actions will show the compatibility of these applications with the MVC.

**As the name implies, the MVC pattern splits your application into three layers:**

*   **The Model stores data:** The Model is strictly a data container that holds values. It does not perform gameplay logic or run calculations.

*   **The View is the interface:** The View formats and renders a graphical presentation of your data onscreen.

*   **The Controller handles logic:** Think of this as the brain. It processes the game data and calculates how the values change at runtime.

**So, to understand this concept more clearly below I have given you a sample code implementation of the basic trinity in an MVC pattern:**

```
// Player Model
public class PlayerModel {
    // Model Events
    public event Action OnMoneyChanged;

    // Model Data
    public int Money => currentMoney;
    private int currentMoney = 100;

    // Add Money
    public void AddMoney(int amount) {
        currentMoney += amount;
        if(currentMoney < 0) currentMoney = 0;
        OnMoneyChanged?.Invoke();
    }
}

// Player View
public class PlayerView : MonoBehaviour {
    [Header("UI References")]
    [SerializeField] private TextMeshProUGUI moneyBar;

    // Current Model
    private PlayerModel currentModel;

    // Set Model
    public void SetModel(PlayerModel model) {
        if(currentModel != null)
            return;

        currentModel = model;
        currentModel.OnMoneyChanged += OnMoneyChangedHandler;
    }

    // On View Destroy
    private void OnDestroy() {
        if(currentModel != null) {
            currentModel.OnMoneyChanged -= OnMoneyChangedHandler;
        }
    }

    // Update Money Bar
    private void UpdateMoney(int money) {
        moneyBar.SetText(money.ToString("N0"));
    }

    // Handle Money Change
    private void OnMoneyChangedHandler() {
        UpdateMoney(currentModel.Money);
    }
}

// Player Controller
public class PlayerController {
    private PlayerModel currentModel;
    private PlayerView currentView;

    // Controller Constructor
    public PlayerController(PlayerView view, PlayerModel model = null) {
        // Setup Model and View for Presenter
        currentModel = model == null ? new PlayerModel() : model;
        currentView = view;
        currentView.SetModel(currentModel);
    }

    // Add Money
    public void AddMoney(int amount) {
        if(currentModel == null)
            return;

        currentModel.AddMoney(amount);
    }
}
```

Next, let's look at a **different implementation** of a similar approach - **MVP**.

### [](https://dev.to/devsdaddy/organizing-architecture-for-games-on-unity-laying-out-the-important-things-that-matter-4d4p#model-view-presenter-mvp) Model View Presenter (MVP)

The traditional **MVC** pattern would require View-specific code to listen for any changes in the Model’s data at runtime. In contrast to this, some developers have decided to take a slightly different route, giving access to data for presentation only upon request from the user with a stricter management approach.

[![Image 5: Unity Patterns - MVP](https://media2.dev.to/dynamic/image/width=800%2Cheight=%2Cfit=scale-down%2Cgravity=auto%2Cformat=auto/https%3A%2F%2Fupday.github.io%2Fimages%2Fblog%2Fmodel_view_presenter%2Fmvp.png%2520align%3D)](https://media2.dev.to/dynamic/image/width=800%2Cheight=%2Cfit=scale-down%2Cgravity=auto%2Cformat=auto/https%3A%2F%2Fupday.github.io%2Fimages%2Fblog%2Fmodel_view_presenter%2Fmvp.png%2520align%3D)

**MVP still preserves the separation of concerns** with three distinct application layers. However, it slightly changes each part’s responsibilities.

In MVP, the Presenter acts as the Controller and extracts data from the model and then formats it for display in the view. MVP switches the layer that handles input. Instead of the Controller, the View is responsible for handling user input.

**And not to be unsubstantiated, let's just look at some sample code to help you understand the difference between MVC and MVP:**

```
// Player Model
public class PlayerModel {
    // Model Events
    public event Action OnMoneyChanged;

    // Model Data
    public int Money => currentMoney;
    private int currentMoney = 100;

    // Add Money
    public void AddMoney(int amount) {
        currentMoney += amount;
        if(currentMoney < 0) currentMoney = 0;
        OnMoneyChanged?.Invoke();
    }
}

// Player View
public class PlayerView : MonoBehaviour {
    [Header("UI References")]
    [SerializeField] private TextMeshProUGUI moneyBar;

    // Update Money Bar
    public void UpdateMoney(int money) {
        moneyBar.SetText(money.ToString("N0"));
    }
}

// Player Presenter
public class PlayerPresenter {
    private PlayerModel currentModel;
    private PlayerView currentView;

    // Presenter Constructor
    public PlayerPresenter(PlayerView view, PlayerModel model = null) {
        // Setup Model and View for Presenter
        currentModel = model == null ? new PlayerModel() : model;
        currentView = view;

        // Add Listeners
        currentModel.OnMoneyChanged += OnMoneyChangedHandler;
        OnMoneyChangedHandler();
    }

    // Add Money
    public void AddMoney(int amount) {
        if(currentModel == null)
            return;

        currentModel.AddMoney(amount);
    }

    // Presenter Destructor
    ~PlayerPresenter() {
        if(currentModel != null) {
            currentModel.OnMoneyChanged -= OnMoneyChangedHandler;
        }
    }

    // Handle Money Change
    private void OnMoneyChangedHandler() {
        currentView.UpdateMoney(currentModel.Money);
    }
}
```

Most often this pattern **also uses the observer pattern** to pass events between the **Presenter** and the **View**. It also happens that passive patterns are used, which mainly store data, and computations are performed by the **Presenter**.

Next we'll look at a slightly more modern approach, which also sort of grew out of the **MVC concept - namely MVVM**. This approach is used quite often nowadays, especially for designing games with a lot of user interfaces.

### [](https://dev.to/devsdaddy/organizing-architecture-for-games-on-unity-laying-out-the-important-things-that-matter-4d4p#model-view-viewmodel-mvvm) Model View ViewModel (MVVM)

**MVVM** stands for **Model-View-ViewModel**. It is a software application architechture designed to decouple view logic from business logic when building software. This is good practice for a number of reasons including reusability, maintainability, and speed of development.

[![Image 6: Unity Patterns - MVVM](https://media2.dev.to/dynamic/image/width=800%2Cheight=%2Cfit=scale-down%2Cgravity=auto%2Cformat=auto/https%3A%2F%2Fi.stack.imgur.com%2FUXK4E.png%2520align%3D)](https://media2.dev.to/dynamic/image/width=800%2Cheight=%2Cfit=scale-down%2Cgravity=auto%2Cformat=auto/https%3A%2F%2Fi.stack.imgur.com%2FUXK4E.png%2520align%3D)

**Let's understand what the MVVM components are here:**

*   **The model, just as in classic MVC** - represents the data logic and description of the fundamental data required for the application to work;

*   **View** - is a subscriber to the event of changing values of properties or commands provided by **View Model**. In case a property has changed in **View Model**, it notifies all subscribers about it, and **View**, in turn, requests the updated property value from **View Model**. In case the user affects any UI element, View invokes the corresponding command provided by View Model.

*   **View Model** - is, on the one hand, an abstraction of View, and on the other hand, a wrapper of data from Model to be bound. That is, it contains the Model converted to a View, as well as commands that the View can use to affect the Model.

Also some **Bindings** intermediary classes act as a glue between **ViewModel** and **View**, or sometimes **Reactive Fields** are used instead, **but there the approach is a bit different, corresponding to the Reactive Programming approach (which we will talk about another time).**

**Building an MVVM architecture looks a bit more complicated than classical approaches, so I recommend you to consider the ready-made Unity MVVM framework as examples:**

[https://github.com/push-pop/Unity-MVVM/](https://github.com/push-pop/Unity-MVVM/)

### [](https://dev.to/devsdaddy/organizing-architecture-for-games-on-unity-laying-out-the-important-things-that-matter-4d4p#entity-component-system-ecs) Entity Component System (ECS)

This is a software architectural pattern that is most often used in video game development to represent objects in the game world. ECS includes objects consisting of data components and systems that operate on those components. **As a rule, ECS is convenient for those who have worked with component-object programming and is closer in paradigm to it than to classical OOP.**

[![Image 7: Unity ECS](https://media2.dev.to/dynamic/image/width=800%2Cheight=%2Cfit=scale-down%2Cgravity=auto%2Cformat=auto/https%3A%2F%2Fhabrastorage.org%2Fr%2Fw1560%2Fgetpro%2Fhabr%2Fupload_files%2F3fd%2F5bc%2F544%2F3fd5bc5442b03a20d52a8003576056d4.png%2520align%3D)](https://media2.dev.to/dynamic/image/width=800%2Cheight=%2Cfit=scale-down%2Cgravity=auto%2Cformat=auto/https%3A%2F%2Fhabrastorage.org%2Fr%2Fw1560%2Fgetpro%2Fhabr%2Fupload_files%2F3fd%2F5bc%2F544%2F3fd5bc5442b03a20d52a8003576056d4.png%2520align%3D)

In simple words, **ECS** (in the case of Unity we will consider DOTS) is a list of technologies that together allow you to conjure up and speed up your project tenfold. **If you look a little deeper at DOTS level, there are two rules that allow you to achieve this:**

*   If you manage the data properly, it will be easier for the processor to process it, and if it's easier to process, it will be easier for the players to live with.

*   The number of processor cores is increasing, but the code of an average programmer does not use all the processor cores. And this leads to poor resource allocation.

*   **ECS** prioritizes data and data handling over everything else. This changes the approach to memory and resource allocation in general.

**So what is ECS:**

*   **Entity** - Like an objects in real life (for example cat, mom, bike, car etc.);

*   **Component** - A special part of your entity (like a tail for cat, wheel for car etc.);

*   **System** - The logic that governs all entities that have one set of components or another. (For example - a cat tail - for ballance, a wheel for smooth car riding);

To transfer the analogy to game objects, your character in the game is Entity. The physics component is Rigidbody, and the system is what will control all the physics in the scene, including your character in the game.

**Code Samples of ECS:**

```
// Camera System Example
[UpdateInGroup(typeof(LateSimulationSystemGroup))]
public partial struct CameraSystem : ISystem
{
    Entity target;    // Target Entity (For Example Player)
    Random random;

    [BurstCompile]
    public void OnCreate(ref SystemState state) {
        state.RequireForUpdate<Execute.Camera>();
        random = new Random(123);
    }

    // Because this OnUpdate accesses managed objects, it cannot be Burst-compiled.
    public void OnUpdate(ref SystemState state) {
       if (target == Entity.Null || Input.GetKeyDown(KeyCode.Space)) {
           var playerQuery = SystemAPI.QueryBuilder().WithAll<Player>().Build();
           var players = playerQuery.ToEntityArray(Allocator.Temp);
           if (players.Length == 0) {
               return;
           }

           target = players[random.NextInt(players.Length)];
        }

        var cameraTransform = CameraSingleton.Instance.transform;
        var playerTransform = SystemAPI.GetComponent<LocalToWorld>(target);
        cameraTransform.position = playerTransform.Position;
        cameraTransform.position -= 10.0f * (Vector3)playerTransform.Forward;  // move the camera back from the player
        cameraTransform.position += new Vector3(0, 5f, 0);  // raise the camera by an offset
        cameraTransform.LookAt(playerTransform.Position);
    }
}
```

**For more information visit official tutorials repo:**

[https://github.com/Unity-Technologies/EntityComponentSystemSamples/](https://github.com/Unity-Technologies/EntityComponentSystemSamples/)

### [](https://dev.to/devsdaddy/organizing-architecture-for-games-on-unity-laying-out-the-important-things-that-matter-4d4p#singleton) Singleton

Singleton pattern is widely used in software development. It ensures that only one instance of a class is created and provides a global access point for the resources it provides.

[![Image 8: Unity Patterns - Singleton](https://media2.dev.to/dynamic/image/width=800%2Cheight=%2Cfit=scale-down%2Cgravity=auto%2Cformat=auto/https%3A%2F%2Fmedia.geeksforgeeks.org%2Fwp-content%2Fuploads%2F20231207174652%2FScreenshot-2023-12-07-174635.png%2520align%3D)](https://media2.dev.to/dynamic/image/width=800%2Cheight=%2Cfit=scale-down%2Cgravity=auto%2Cformat=auto/https%3A%2F%2Fmedia.geeksforgeeks.org%2Fwp-content%2Fuploads%2F20231207174652%2FScreenshot-2023-12-07-174635.png%2520align%3D)

It is used when you need to create one and only one object of a class for the whole application life cycle and access to it from different parts of the code.

An example of using this pattern is the creation of the application settings class. Obviously, application settings are the only ones of their kind for the whole application.

```
// Lazy Load Singleton
public abstract class MySingleton<T> : MonoBehaviour where T : MonoBehaviour
{
    private static readonly Lazy<T> LazyInstance = new Lazy<T>(CreateSingleton);

    public static T Main => LazyInstance.Value;

    private static T CreateSingleton()
    {
        var ownerObject = new GameObject($"__{typeof(T).Name}__");
        var instance = ownerObject.AddComponent<T>();
        DontDestroyOnLoad(ownerObject);
        return instance;
    }
}
```

You can read More about [Singleton in Unity in my another tutorial](https://dev.to/devsdaddy/everything-you-need-to-know-about-singleton-in-c-and-unity-n40).

### [](https://dev.to/devsdaddy/organizing-architecture-for-games-on-unity-laying-out-the-important-things-that-matter-4d4p#target-action) Target Action

The next pattern we will consider is called **Target-Action**. Usually the user interface of an application consists of several graphical objects, and often controls are used as such objects. These can be buttons, switches, text input fields. The role of a control in the user interface is quite simple: it perceives the user's intention to do some action and instructs another object to process this request. The Target-Action pattern is used to communicate between the control and the object that can process the request.

### [](https://dev.to/devsdaddy/organizing-architecture-for-games-on-unity-laying-out-the-important-things-that-matter-4d4p#observer) Observer

In the **Observer pattern**, one object notifies other objects of changes in its state. Objects linked in this way do not need to know about each other - this is a loosely coupled (and therefore flexible) code. This pattern is most often used when we need to notify an "observer" about changes in the properties of our object or about the occurrence of any events in this object. Usually, the observer "registers" its interest in the state of another object.

```
// Simple Subject Example
public class Subject: MonoBehaviour
{
    public event Action ThingHappened;

    public void DoThing()
    {
        ThingHappened?.Invoke();
    }
}

// Simple Observer Example
public class Observer : MonoBehaviour
{
    [SerializeField] private Subject subjectToObserve;

    private void OnThingHappened()
    {
        // any logic that responds to event goes here
        Debug.Log("Observer responds");
    }

    private void Awake()
    {
        if (subjectToObserve != null)
        {
            subjectToObserve.ThingHappened += OnThingHappened;
        }
    }

    private void OnDestroy()
    {
        if (subjectToObserve != null)
        {
            subjectToObserve.ThingHappened -= OnThingHappened;
        }
    }
}
```

### [](https://dev.to/devsdaddy/organizing-architecture-for-games-on-unity-laying-out-the-important-things-that-matter-4d4p#command) Command

**Command** is a behavioral design pattern that allows actions to be represented as objects. Encapsulating actions as objects enables you to create a flexible and extensible system for controlling the behavior of GameObjects in response to user input. This works by encapsulating one or more method calls as a “command object” rather than invoking a method directly. Then you can store these command objects in a collection, like a queue or a stack, which works as a small buffer.

```
// Simple Command Interface
public interface ICommand
{
    void Execute();
    void Undo();
}

// Simple Command Invoker Realisation
public class CommandInvoker
{
    // stack of command objects to undo
    private static Stack<ICommand> _undoStack = new Stack<ICommand>();

    // second stack of redoable commands
    private static Stack<ICommand> _redoStack = new Stack<ICommand>();

    // execute a command object directly and save to the undo stack
    public static void ExecuteCommand(ICommand command)
    {
        command.Execute();
        _undoStack.Push(command);

        // clear out the redo stack if we make a new move
        _redoStack.Clear();
    }

    public static void UndoCommand()
    {
        if (_undoStack.Count > 0)
        {
            ICommand activeCommand = _undoStack.Pop();
            _redoStack.Push(activeCommand);
            activeCommand.Undo();
        }
    }

    public static void RedoCommand()
    {
        if (_redoStack.Count > 0)
        {
            ICommand activeCommand = _redoStack.Pop();
            _undoStack.Push(activeCommand);
            activeCommand.Execute();
        }
    }
  }
}
```

Storing command objects in this way enables you to control the timing of their execution by potentially delaying a series of actions for later playback. Similarly, you are able to redo or undo them and add extra flexibility to control each command object’s execution.

## [](https://dev.to/devsdaddy/organizing-architecture-for-games-on-unity-laying-out-the-important-things-that-matter-4d4p#reducing-code-cohesion-in-the-project) Reducing code cohesion in the project

Linking and reducing dependencies in complex development is one of the important tasks, as it allows you to achieve the very modularity and flexibility of your code. There are a lot of different approaches for this purpose, but I will focus on a couple of them - **Depedency Injection** and **Pub Sub**.

[![Image 9](https://media2.dev.to/dynamic/image/width=800%2Cheight=%2Cfit=scale-down%2Cgravity=auto%2Cformat=auto/https%3A%2F%2Fcdn.hashnode.com%2Fres%2Fhashnode%2Fimage%2Fupload%2Fv1712604614497%2F38b38b41-f066-4001-b522-54a438092e1e.png%2520align%3D)](https://media2.dev.to/dynamic/image/width=800%2Cheight=%2Cfit=scale-down%2Cgravity=auto%2Cformat=auto/https%3A%2F%2Fcdn.hashnode.com%2Fres%2Fhashnode%2Fimage%2Fupload%2Fv1712604614497%2F38b38b41-f066-4001-b522-54a438092e1e.png%2520align%3D)

### [](https://dev.to/devsdaddy/organizing-architecture-for-games-on-unity-laying-out-the-important-things-that-matter-4d4p#dependency-injection) Dependency Injection

**Dependency injection** is a style of object customization in which object fields are set by an external entity. In other words, objects are customized by external entities. DI is an alternative to self-customizing objects.

```
// Simple Depedency Injection Class
public class Player
{
    [Dependency]
    public IControlledCharacter PlayerHero { private get; set; }

    [Dependency]
    public IController Controller { private get; set; }

    private void Update()
    {
        if (Controller.LeftCmdReceived())
            PlayerHero.MoveLeft();
        if (Controller.RightCmdReceived())
            PlayerHero.MoveRight();
    }
}

// Simple Game Installer
public class GameInstaller : MonoBehaviour {
    public GameObject controller;

    private void Start() {
        // This is an abstract DI Container.
        var container = new Container();
        container.RegisterType<Player>(); // Register Player Type
        container.RegisterType<IController, KeyboardController>(); // Register Controller Type
        container.RegisterSceneObject<IControlledCharacter>(controller);

        // Here we call to resolve all depedencies inside player
        // using our container
        container.Resolve<Player>();
    }
}
```

**What does working with Dependency Injection give us?**

*   **By accessing the container, we will get an already assembled object with all its dependencies.** As well as dependencies of its dependencies, dependencies of dependencies of dependencies of its dependencies, etc;

*   **The class dependencies are very clearly highlighted in the code**, which greatly enhances readability. One glance is enough to understand what entities the class interacts with. Readability, in my opinion, is a very important quality of code, if not the most important at all. Easy to read -> easy to modify -> less likely to introduce bugs -> code lives longer -> development moves faster and costs cheaper;

*   **The code itself is simplified.** Even in our trivial example we managed to get rid of searching for an object in the scene tree. And how many such similar pieces of code are scattered in real projects? The class became more focused on its main functionality;

*   **There is additional flexibility** - changing the container customization is easy. All changes responsible for linking your classes together are localized in one place;

*   From this flexibility (and the use of interfaces to reduce coupling) stems the ease of unit testing your classes;

For example you can use [this lightweight DI Framework](https://github.com/modesttree/Zenject) for your games.

### [](https://dev.to/devsdaddy/organizing-architecture-for-games-on-unity-laying-out-the-important-things-that-matter-4d4p#pub-sub-pattern) Pub / Sub Pattern

**The Pub-sub pattern is a variation of the Observer pattern.** Based on its name, the pattern has two components Publisher and Subscriber. Unlike Observer, communication between the objects is performed through the **Event Channel**.

The **Publisher** throws its events into the **Event Channel**, and the **Subscriber** subscribes to the desired event and listens to it on the bus, ensuring that there is no direct communication between the **Subscriber** and the **Publisher**.

[![Image 10](https://media2.dev.to/dynamic/image/width=800%2Cheight=%2Cfit=scale-down%2Cgravity=auto%2Cformat=auto/https%3A%2F%2Fhabrastorage.org%2Fr%2Fw1560%2Ffiles%2F39b%2F7f9%2F806%2F39b7f98064b5458e9e2837cca15e3525.jpg%2520align%3D)](https://media2.dev.to/dynamic/image/width=800%2Cheight=%2Cfit=scale-down%2Cgravity=auto%2Cformat=auto/https%3A%2F%2Fhabrastorage.org%2Fr%2Fw1560%2Ffiles%2F39b%2F7f9%2F806%2F39b7f98064b5458e9e2837cca15e3525.jpg%2520align%3D)

Thus we can emphasize the main distinguishing features between Pub-sub and Observer: lack of direct communication between objects objects signal each other by events, not by object states possibility to subscribe to different events on one object with different handlers

```
// Player Class (Publisher)
public class Player : MonoBehaviour, IEntity {
    // Take Damage
    public TakeDamage(int damage){
        // Publish Event to our Event Channel
        EventMessenger.Main.Publish(new DamagePayload {
            Target: this,
            Damage: damage
        });
    }
}

// UI Class (Subscriber)
public class UI : MonoBehaviour {
    private void Awake() {
        EventMessenger.Main.Subscribe<DamagePayload>(OnDamageTaked);
    }

    private void OnDestroy() {
        EventMessenger.Main.Unsubscribe<DamagePayload>(OnDamageTaked);
    }

    private void OnDamageTaked(DamagePayload payload) {
        // Here we can update our UI. We also can filter it by Target in payload
    }
}
```

You also see [my variation of Pub/Sub Pattern (variation of Observer) with Reactivity](https://github.com/DevsDaddy/UIFramework).

## [](https://dev.to/devsdaddy/organizing-architecture-for-games-on-unity-laying-out-the-important-things-that-matter-4d4p#in-conclusion) In conclusion

Organizing the right architecture will greatly help you increase the chances of seeing your project through to completion, especially if you are planning something large-scale. There are a huge number of different approaches and it is impossible to say that any of them can be wrong. You need to remember that everything is built individually and each approach has its pros and cons, and what will suit your project - it is clear only to you.

**I will be glad to help you in the realization of your ideas and answer all your questions. Thank you for reading and good luck!**

* * *

[My Discord](https://discord.gg/a7cHDtfYbv) | [My Blog](https://devsdaddy.hashnode.dev/) | [My GitHub](https://github.com/DevsDaddy) | [Buy me a Beer](https://boosty.to/devsdaddy)



