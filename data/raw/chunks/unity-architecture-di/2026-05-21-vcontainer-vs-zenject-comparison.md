---
title: VContainer vs Zenject — Official Comparison
slug: 2026-05-21-vcontainer-vs-zenject-comparison
created_at: '2026-05-21T10:39:00+09:00'
status: draft
source_type: url
lang: ko
tags:
- vcontainer
- zenject
- dependency-injection
- unity
source_url: https://vcontainer.hadashikick.jp/comparing/comparing-to-zenject
fetched_at: '2026-05-21T10:39:00+09:00'
summary: VContainer는 Zenject 대비 성능과 구현 가독성, 단순한 DI 선언 측면에서 우위를 갖는 대안이다. 리플렉션·어설션을
  컨테이너 빌드 단계로 격리하고 씬 시작 시 모든 GameObject를 탐색하지 않으며, MonoBehaviour 주입 대신 주입을 권장하고 빌더
  체이닝(Register/Lifetime, RegisterFactory 등)으로 API가 더 간결하다. 다만 Signal, Memory Pool,
  WithId, Resource 경로 바인딩 같은 일부 Zenject 기능은 지원하지 않아 메시징·풀링·리소스 로딩은 VitalRouter, MessagePipe,
  LoadAsync 등 외부 수단으로 보완해야 한다.
---
## TL;DR
VContainer는 Zenject 대비 성능과 구현 가독성, 단순한 DI 선언 측면에서 우위를 갖는 대안이다. 리플렉션·어설션을 컨테이너 빌드 단계로 격리하고 씬 시작 시 모든 GameObject를 탐색하지 않으며, MonoBehaviour 주입 대신 주입을 권장하고 빌더 체이닝(Register/Lifetime, RegisterFactory 등)으로 API가 더 간결하다. 다만 Signal, Memory Pool, WithId, Resource 경로 바인딩 같은 일부 Zenject 기능은 지원하지 않아 메시징·풀링·리소스 로딩은 VitalRouter, MessagePipe, LoadAsync 등 외부 수단으로 보완해야 한다.

Title: Comparing to Zenject | VContainer

URL Source: https://vcontainer.hadashikick.jp/comparing/comparing-to-zenject

Markdown Content:
Zenject is awesome. However, VContainer has the following advantages:

*   Good performance.
*   Most parts of reflections and assertions are isolated to the Container's build stage.
*   Easy to read implementation.
*   VContainer has carefully selected features and does not register data-oriented objects in the container or actively inject the View component. This prevents the DI declaration from becoming overly complex.
    *   Zenject is often used to inject into dynamic or datacentric objects, but this is complicated
    *   In VContainer, injection of MonoBehaviour is recommended over injection into MonoBehaviour.
    *   Zenject looks up all GameObjects in reflection when the scene starts, but this operation is expensive; VContainer does not do this.

## Code size (v1.3.0)[​](https://vcontainer.hadashikick.jp/comparing/comparing-to-zenject#code-size-v130 "Direct link to Code size (v1.3.0)")

## API difference[​](https://vcontainer.hadashikick.jp/comparing/comparing-to-zenject#api-difference "Direct link to API difference")

### Basic[​](https://vcontainer.hadashikick.jp/comparing/comparing-to-zenject#basic "Direct link to Basic")

| Zenject | VContainer |
| --- | --- |
| Container.Bind<Service>() .AsTransient() | builder.Register<Service>(Lifetime.Transient) |
| Container.Bind<Service>() .AsCached() | builder.Register<Service>(Lifetime.Scoped) |
| Container.Bind<Service>() .AsSingle() | builder.Register<Service>(Lifetime.Singleton) |
| Container.Bind<IService>() .To<Service> .AsCached() | builder.Register<IService,Service>(Lifetime.Scoped) |
| Container.Bind( typeof(IInitializable), typeof(IDisposable)) .To<Service>() .AsCached() | builder.Register<Service>(Lifetime.Scoped) .As<IInitializable,IDisposable>() |
| Container.BindInterfacesTo<Service>() .AsCached() | builder.Register<Service>(Lifetime.Scoped) .AsImplementedInterfaces() |
| Container.BindInterfacesAndSelfTo<Foo>() .AsCached() | builder.Register<Service>(Lifetime.Scoped) .AsImplementedInterfaces() .AsSelf() |
| Container.BindInstance(obj) | builder.RegisterInstance(obj) |
| Container.Bind<IService>() .FromInstance(obj) | builder.RegisterInstance<IService>(obj) |
| Container.Bind( typeof(IService1), typeof(IService2)) .FromInstance(obj) | builder.RegisterInstance(obj) .As<IService1,IService2>() |
| Container.Bind( typeof(IService1), typeof(IService2)) .FromInstance(obj) | builder.RegisterInstance(obj) .As<IService1,IService2>() |
| Container.BindInterfacesTo<Service>() .FromInstance(obj) | builder.RegisterInstance(obj) .AsImplementedInterfaces() |
| Container.BindInterfacesAndSelfTo<Service>() .FromInstance(obj) | builder.RegisterInstance(obj) .AsImplementedInterfaces() .AsSelf() |

### Component[​](https://vcontainer.hadashikick.jp/comparing/comparing-to-zenject#component "Direct link to Component")

| Zenject | VContainer |
| --- | --- |
| Container.Bind<Foo>() .FromComponentInHierarchy() .AsCached(); | builder.RegisterComponentInHierarchy<Foo>() |
| Container.Bind<Foo>() .FromComponentInNewPrefab(prefab) .AsCached() | builder.RegisterComponentInNewPrefab(prefab, Lifetime.Scoped) |
| Container.Bind<Foo>() .FromNewComponentOnNewGameObject() .AsCached() .WithGameObjectName("Foo1") | builder.RegisterComponentOnNewGameObject<Foo>( Lifetime.Scoped, "Foo1") |
| .UnderTransform(parentTransform) | .UnderTransform(parentTransform) |
| .UnderTransform(() => parentTransform) | .UnderTransform(() => parentTransform) |

### Factory[​](https://vcontainer.hadashikick.jp/comparing/comparing-to-zenject#factory "Direct link to Factory")

#### Factory with parameter[​](https://vcontainer.hadashikick.jp/comparing/comparing-to-zenject#factory-with-parameter "Direct link to Factory with parameter")

Zenject

`public class Enemy{    readonly float speed;    public Enemy(float speed)    {        this.speed = speed;    }    public class Factory : PlaceholderFactory<float, Enemy>;    {    }}Container.BindFactory<float, Enemy, Enemy.Factory>();`

VContainer

`public class Enemy{    readonly float speed;    public Enemy(float speed)    {        this.speed = speed;    }}builder.RegisterFactory<float, Enemy>(speed => new Enemy(speed));`

#### Factory with parameter & resolve dependency at runtime[​](https://vcontainer.hadashikick.jp/comparing/comparing-to-zenject#factory-with-parameter--resolve-dependency-at-runtime "Direct link to Factory with parameter & resolve dependency at runtime")

Zenject

`public class Enemy{    readonly Player player;    readonly float speed;    public Enemy(float speed, Player player)    {        this.player = player;        this.speed = speed;    }    public class Factory : PlaceholderFactory<float, Enemy>;    {    }}Container.BindFactory<float, Enemy, Enemy.Factory>();`

VContainer

`public class Enemy{    readonly Player player;    readonly float speed;    public Enemy(float speed, Player player)    {        this.player = player;        this.speed = speed;    }}builder.RegisterFactory<float, Enemy>(container =>{    var player = container.Resolve<Player>();    return speed => new Enemy(speed, player);}, Lifetime.Scoped);`

#### Factory with prefab[​](https://vcontainer.hadashikick.jp/comparing/comparing-to-zenject#factory-with-prefab "Direct link to Factory with prefab")

Zenject

`public class Enemy : MonoBehaviour{    Player player;    [Inject]    public void Construct(Player player)    {        this.player = player;    }    public class Factory : PlaceholderFactory<Enemy>    {    }}Container.BindFactory<Enemy, Enemy.Factory>()    .FromComponentInNewPrefab(enemyPrefab);`

VContainer

`public class Enemy : MonoBehaviour{    Player player;    public void Construct(Player player)    {        this.player = player;    }}builder.RegisterFactory<Enemy>(container =>{    var player = container.Resolve<Player>();    return () =>    {        var enemy = Instantiate(enemyPrefab);        enemy.Construct(player);        return enemy;    };}, Lifetime.Scoped);`

### Misc[​](https://vcontainer.hadashikick.jp/comparing/comparing-to-zenject#misc "Direct link to Misc")

| Zenject | VContainer |
| --- | --- |
| **Signal** | **Not supported** The central messaging pattern is useful, but depends largely on the style of the project, and the preferred implementation will vary. You can choose any implementation of [VitalRouter](https://github.com/hadashiA/VitalRouter), [Cysharp/MessagePipe](https://github.com/Cysharp/MessagePipe) or etc. |
| **Memory Pool** | **Not supported** Currently, any Memory pool implementation is not embed. Please inject the implementation according to the purpose of the project into Factory etc. |
| Container.Bind<Foo>() .FromComponentInNewPrefabResource("Some/Path/Foo") | **Not Supported** We should load Resources using LoadAsync family. You can use RegisterInstance() etc after loading the Resource. |
| Container.Bind<Foo>() .WithId("foo") .AsCached() | **Not supported** Duplicate type Resolve is not recommended. You can instead use type-specific Register builder.Register(Lifetime.Scoped).WithParameter("foo", foo) |



