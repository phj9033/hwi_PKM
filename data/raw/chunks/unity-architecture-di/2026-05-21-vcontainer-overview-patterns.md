---
title: VContainer — About & Architecture
slug: 2026-05-21-vcontainer-overview-patterns
created_at: '2026-05-21T10:37:32+09:00'
status: draft
source_type: url
lang: ko
tags:
- dependency-injection
- unity
- ioc-container
- game-development
source_url: https://vcontainer.hadashikick.jp/
fetched_at: '2026-05-21T10:37:32+09:00'
summary: VContainer는 Unity용 DI 컨테이너로, Zenject 대비 5~10배 빠른 Resolve 성능과 Resolve 시 제로
  GC 할당, 불변·스레드 안전 컨테이너, 그리고 Plain C# 엔트리포인트·유연한 스코핑·UniTask 통합 같은 기능을 제공한다. 이는 공개된
  벤치마크(10,000회 반복, IL2CPP macOS) 결과와 Roslyn Source Generator 기반 코드 생성 최적화, MonoBehaviour
  의존을 분리하는 설계 원칙에 근거한다. 다만 기본 동작은 런타임 리플렉션이며 최고 성능을 위해서는 CodeGen 모드 적용이 필요하고, ECS
  통합은 아직 beta 단계라는 한계가 있다.
---
## TL;DR
VContainer는 Unity용 DI 컨테이너로, Zenject 대비 5~10배 빠른 Resolve 성능과 Resolve 시 제로 GC 할당, 불변·스레드 안전 컨테이너, 그리고 Plain C# 엔트리포인트·유연한 스코핑·UniTask 통합 같은 기능을 제공한다. 이는 공개된 벤치마크(10,000회 반복, IL2CPP macOS) 결과와 Roslyn Source Generator 기반 코드 생성 최적화, MonoBehaviour 의존을 분리하는 설계 원칙에 근거한다. 다만 기본 동작은 런타임 리플렉션이며 최고 성능을 위해서는 CodeGen 모드 적용이 필요하고, ECS 통합은 아직 beta 단계라는 한계가 있다.

Title: About | VContainer

URL Source: https://vcontainer.hadashikick.jp/

Markdown Content:
The extra fast DI (Dependency Injection) for Unity Game Engine. "V" means making Unity's initial "U" more thinner and solid..!

*   **Fast Resolve:** Basically [5-10x faster](https://vcontainer.hadashikick.jp/#performance) than Zenject.
*   **Minimum GC Allocation:** In Resolve, we have **zero allocation** without spawned instances.
*   **Small code size:** Few internal types and few .callvirt.
*   **Assisting correct DI way:** Provides simple and transparent API, and carefully select features. This prevents the DI declaration from becoming overly complex.
*   **Immutable Container:** Thread safety and robustness.

#### Features[​](https://vcontainer.hadashikick.jp/#features "Direct link to Features")

*   [Constructor Injection](https://vcontainer.hadashikick.jp/resolving/constructor-injection) / [Method Injection](https://vcontainer.hadashikick.jp/resolving/method-injection) / [Property & Field Injection](https://vcontainer.hadashikick.jp/resolving/property-field-injection)
*   [Plain C# entry point on own PlayerLoopSystem](https://vcontainer.hadashikick.jp/integrations/entrypoint)
*   [Flexible scoping](https://vcontainer.hadashikick.jp/scoping/lifetime-overview)
    *   Application can freely create nested Lifetime Scope with any async way for you like.

*   [Accelerated mode with Roslyn Source Generator](https://vcontainer.hadashikick.jp/optimization/source-generator)
*   [Diagnostics Window](https://vcontainer.hadashikick.jp/diagnostics/diagnostics-window)
*   [UniTask Integration](https://vcontainer.hadashikick.jp/integrations/unitask)
*   [ECS Integration](https://vcontainer.hadashikick.jp/integrations/ecs)_beta_

## DI + Inversion of Control for Unity[​](https://vcontainer.hadashikick.jp/#di--inversion-of-control-for-unity "Direct link to DI + Inversion of Control for Unity")

![Image 1](https://vcontainer.hadashikick.jp/assets/images/vcontainer@2x-53a84c3f5ff1a1ccc371a2f3eb73977a.png)

DI containers we can make pure C # classes the entry point (not MonoBehaviour). This means that the control flow and other domain logic can be separated from the function of MonoBehaviour as a view component.

Further reading:

*   [Manning | Dependency Injection in .NET](https://www.manning.com/books/dependency-injection-in-dot-net)
*   [Lightweight IoC Container for Unity - Seba's Lab](https://www.sebaslab.com/ioc-container-unity-part-1/)

## Performance[​](https://vcontainer.hadashikick.jp/#performance "Direct link to Performance")

### Benchmark result for 10,000 iterations for each test case (Unity 2019.x / IL2CPP Standalone macOS)[​](https://vcontainer.hadashikick.jp/#benchmark-result-for-10000-iterations-for-each-test-case-unity-2019x--il2cpp-standalone-macos "Direct link to Benchmark result for 10,000 iterations for each test case (Unity 2019.x / IL2CPP Standalone macOS)")

*   By default, both VContainer and Zenject use reflection at runtime.
*   "VContainer (CodeGen)" means optimization by pre-generating IL code of Inject methods by ILPostProcessor. See [Optimization](https://vcontainer.hadashikick.jp/optimization/codegen) section for more information.

### GC Alloc result in the Resolve Complex test case (Unity Editor profiled)[​](https://vcontainer.hadashikick.jp/#gc-alloc-result-in-the-resolve-complex-test-case-unity-editor-profiled "Direct link to GC Alloc result in the Resolve Complex test case (Unity Editor profiled)")

## Basic Usage[​](https://vcontainer.hadashikick.jp/#basic-usage "Direct link to Basic Usage")

First, create a scope. References are automatically resolved for types registered here.

`public class GameLifetimeScope : LifetimeScope{    protected override void Configure(IContainerBuilder builder)    {        builder.RegisterEntryPoint<ActorPresenter>();        builder.Register<CharacterService>(Lifetime.Scoped);        builder.Register<IRouteSearch, AStarRouteSearch>(Lifetime.Singleton);        builder.RegisterComponentInHierarchy<ActorsView>();    }}`

Where definitions of classes are

`public interface IRouteSearch{}public class AStarRouteSearch : IRouteSearch{}public class CharacterService{    readonly IRouteSearch routeSearch;    public CharacterService(IRouteSearch routeSearch)    {        this.routeSearch = routeSearch;    }}`

`public class ActorsView : MonoBehaviour{}`

and

`public class ActorPresenter : IStartable{    readonly CharacterService service;    readonly ActorsView actorsView;    public ActorPresenter(        CharacterService service,        ActorsView actorsView)    {        this.service = service;        this.actorsView = actorsView;    }    void IStartable.Start()    {        // Scheduled at Start () on VContainer's own PlayerLoopSystem.    }}`

*   In this example, the routeSearch of CharacterService is automatically set as the instance of AStarRouteSearch when CharacterService is resolved.
*   Further, VContainer can have a Pure C# class as an entry point. (Various timings such as Start, Update, etc. can be specified.) This facilitates "separation of domain logic and presentation".

### Flexible Scoping with async[​](https://vcontainer.hadashikick.jp/#flexible-scoping-with-async "Direct link to Flexible Scoping with async")

LifetimeScope can dynamically create children. This allows you to deal with the asynchronous resource loading that often occurs in games.

`public void LoadLevel(){    // ... Loading some assets    // Create a child scope    instantScope = currentScope.CreateChild();    // Create a child scope with LifetimeScope prefab    instantScope = currentScope.CreateChildFromPrefab(lifetimeScopePrefab);    // Create a child with additional registration    instantScope = currentScope.CreateChildFromPrefab(        lifetimeScopePrefab,        builder =>        {            // Extra Registrations ...        });    instantScope = currentScope.CreateChild(builder =>    {        // ExtraRegistrations ...    });    instantScope = currentScope.CreateChild(extraInstaller);}public void UnloadLevel(){    instantScope.Dispose();}`

In addition, you can create a parent-child relationship with LifetimeScope in an Additive scene.

`class SceneLoader{    readonly LifetimeScope currentScope;    public SceneLoader(LifetimeScope currentScope)    {        currentScope = currentScope; // Inject the LifetimeScope to which this class belongs    }    IEnumerator LoadSceneAsync()    {        // LifetimeScope generated in this block will be parented by `this.lifetimeScope`        using (LifetimeScope.EnqueueParent(currentScope))        {            // If this scene has a LifetimeScope, its parent will be `parent`.            var loading = SceneManager.LoadSceneAsync("...", LoadSceneMode.Additive);            while (!loading.isDone)            {                yield return null;            }        }    }    // UniTask example    async UniTask LoadSceneAsync()    {        using (LifetimeScope.EnqueueParent(parent))        {            await SceneManager.LoadSceneAsync("...", LoadSceneMode.Additive);        }    }}`

`// LifetimeScopes generated during this block will be additionally Registered.using (LifetimeScope.Enqueue(builder =>{    // Register for the next scene not yet loaded    builder.RegisterInstance(extraInstance);})){    // Loading the scene..}`

See [scoping](https://vcontainer.hadashikick.jp/scoping/lifetime-overview) for more information.

## UniTask[​](https://vcontainer.hadashikick.jp/#unitask "Direct link to UniTask")

`public class FooController : IAsyncStartable{    public async UniTask StartAsync(CancellationToken cancellation)    {        await LoadSomethingAsync(cancellation);        await ...        ...    }}`

`builder.RegisterEntryPoint<FooController>();`

See [integration](https://vcontainer.hadashikick.jp/integrations/unitask) for more information.

## Diagnostics Window[​](https://vcontainer.hadashikick.jp/#diagnostics-window "Direct link to Diagnostics Window")

![Image 2](https://vcontainer.hadashikick.jp/assets/images/screenshot_diagnostics_window-0dd234094c90eff213527b3d30cf939a.png)

See [diagnostics](https://vcontainer.hadashikick.jp/diagnostics/diagnostics-window) for more information.

## Getting Started[​](https://vcontainer.hadashikick.jp/#getting-started "Direct link to Getting Started")

*   [Installation](https://vcontainer.hadashikick.jp/getting-started/installation)
*   [Hello World](https://vcontainer.hadashikick.jp/getting-started/hello-world)
*   [Comparing to Zenject](https://vcontainer.hadashikick.jp/comparing/comparing-to-zenject)



