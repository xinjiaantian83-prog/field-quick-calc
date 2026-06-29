(function () {
  'use strict';

  var sceneGrid = document.getElementById('scene-grid');
  var catalogGrid = document.getElementById('catalog-grid');
  var loadStatus = document.getElementById('load-status');
  var heroVisual = document.getElementById('hero-visual');
  var heroCarousel = document.getElementById('hero-carousel');
  var DETAIL_PAGE = 'outdoor-kitchen-detail.html';
  var DATA_SOURCES = [
    'products/products.json',
    'json/products.json',
  ];

  var HERO = {
    url: 'images/lifestyle/hero-evening-garden-pizza.jpg',
    mobileUrl: 'images/lifestyle/hero-evening-garden-pizza-mobile.jpg',
    label: '夕暮れの庭で家族とピザ窯を囲むGarden Living',
  };

  var SCENES = [
    {
      id: 'pizza-evening',
      category: 'OUTDOOR COOKING',
      title: '夕暮れ、庭でピザを焼く。',
      copy: '火を見ながら焼き上がりを待つ時間まで、家族の思い出になります。',
      quote: '「じぃじ、またピザ作ろう！」',
      image: 'images/lifestyle/hero-evening-garden-pizza.jpg',
      mobileImage: 'images/lifestyle/hero-evening-garden-pizza-mobile.jpg',
      productIds: ['eg3-ab-pk'],
      detailProductId: 'eg3-ab-pk',
      status: 'available',
    },
    {
      id: 'bbq-weekend',
      category: 'OUTDOOR COOKING',
      title: '今日は外で食べようか。',
      copy: '焼くだけではなく、集まるきっかけまでつくる庭のBBQシーン。',
      quote: '「またみんなで集まろう。」',
      image: 'images/lifestyle/g19-pizza-fire-table.jpg',
      productIds: ['eg3-ab-bq'],
      detailProductId: 'eg3-ab-bq',
      status: 'available',
    },
    {
      id: 'slow-smoke',
      category: 'OUTDOOR COOKING',
      title: '待つ時間を楽しむ、燻製の庭。',
      copy: 'すぐに食べるだけではない、香りと会話がゆっくり育つ休日。',
      quote: '「次は何を燻そうか。」',
      image: 'images/lifestyle/g19-fire-pan-deck.jpg',
      productIds: ['eg3-ab-kk'],
      detailProductId: 'eg3-ab-kk',
      status: 'available',
    },
    {
      id: 'dog-garden',
      category: 'DOG GARDEN',
      title: '犬が走れる庭をつくる。',
      copy: '人工芝、フェンス、門扉まで。家族も犬も安心して過ごせる庭へ。',
      quote: '「今日は庭で遊ぼう。」',
      image: 'images/lifestyle/g19-ooya-stone-garden.jpg',
      productIds: [],
      status: 'coming',
    },
    {
      id: 'outdoor-sauna',
      category: 'OUTDOOR SAUNA',
      title: '外気浴まで庭で楽しむ。',
      copy: '夕暮れ、灯り、木の質感。サウナのあとに深呼吸したくなる庭。',
      quote: '「ここで整いたい。」',
      image: 'images/lifestyle/g19-firewood-rack-detail.jpg',
      productIds: [],
      status: 'coming',
    },
    {
      id: 'garden-furniture',
      category: 'GARDEN FURNITURE',
      title: '座る場所があるだけで、庭は部屋になる。',
      copy: 'テーブル、チェア、灯り。外で過ごす理由を少しずつ増やします。',
      quote: '「コーヒー、外で飲もうか。」',
      image: 'images/lifestyle/g19-antique-bricks-lifestyle.jpg',
      productIds: [],
      status: 'coming',
    },
  ];

  function formatYen(value) {
    if (typeof value !== 'number' || !isFinite(value)) {
      return '価格はお問い合わせください';
    }
    return '¥' + value.toLocaleString('ja-JP') + '（税込）';
  }

  function text(value) {
    return value === null || value === undefined || value === '' ? '未確認' : String(value);
  }

  function productMap(products) {
    return products.reduce(function (map, product) {
      map[product.id] = product;
      return map;
    }, {});
  }

  function detailUrl(productId) {
    return DETAIL_PAGE + '?id=' + encodeURIComponent(productId);
  }

  function loadProducts() {
    return DATA_SOURCES.reduce(function (promise, source) {
      return promise.catch(function () {
        return fetch(source, { cache: 'no-store' }).then(function (response) {
          if (!response.ok) throw new Error('load failed');
          return response.json();
        });
      });
    }, Promise.reject());
  }

  function renderHero() {
    if (!heroVisual || !heroCarousel) return;
    heroCarousel.textContent = '';
    heroVisual.classList.remove('is-loading');
    heroVisual.classList.add('has-images');
    heroCarousel.innerHTML =
      '<figure class="hero-slide is-active">' +
        '<picture>' +
          '<source media="(max-width: 720px)" srcset="' + HERO.mobileUrl + '">' +
          '<img src="' + HERO.url + '" alt="' + HERO.label + '">' +
        '</picture>' +
        '<figcaption>' + HERO.label + '</figcaption>' +
      '</figure>';
  }

  function renderUsedProduct(product) {
    var basic = product.basic || {};
    var pricing = product.pricing || {};
    return '' +
      '<li class="used-product">' +
        '<div>' +
          '<p class="used-maker">' + text(basic.manufacturer) + '</p>' +
          '<h4>' + text(basic.product_name) + '</h4>' +
          '<p class="used-price">' + formatYen(pricing.manufacturer_price_in_tax) + '</p>' +
        '</div>' +
        '<a href="' + detailUrl(product.id) + '">商品を見る</a>' +
      '</li>';
  }

  function createSceneCard(scene, productsById) {
    var products = scene.productIds.map(function (id) { return productsById[id]; }).filter(Boolean);
    var picture = scene.mobileImage
      ? '<picture><source media="(max-width: 720px)" srcset="' + scene.mobileImage + '"><img src="' + scene.image + '" alt="' + scene.title + '" loading="lazy"></picture>'
      : '<img src="' + scene.image + '" alt="' + scene.title + '" loading="lazy">';
    var productList = products.length
      ? products.map(renderUsedProduct).join('')
      : '<li class="used-product is-coming"><div><p class="used-maker">' + scene.category + '</p><h4>使用商品を準備中</h4><p class="used-price">掲載準備が整い次第、追加します。</p></div><span>COMING SOON</span></li>';

    var article = document.createElement('article');
    article.className = 'scene-card' + (scene.status === 'coming' ? ' is-coming' : '');
    article.innerHTML =
      '<div class="scene-photo">' + picture + '</div>' +
      '<div class="scene-content">' +
        '<p class="scene-category">' + scene.category + '</p>' +
        '<h3>' + scene.title + '</h3>' +
        '<p>' + scene.copy + '</p>' +
        '<blockquote>' + scene.quote + '</blockquote>' +
        '<div class="used-products-block">' +
          '<p class="used-title">使用している商品</p>' +
          '<ul class="used-products">' + productList + '</ul>' +
        '</div>' +
      '</div>';
    return article;
  }

  function createCatalogCard(product) {
    var basic = product.basic || {};
    var seo = product.seo || {};
    var pricing = product.pricing || {};
    var article = document.createElement('article');
    article.className = 'catalog-card';
    article.innerHTML =
      '<p class="product-model">' + text(basic.category) + '</p>' +
      '<h3>' + text(basic.product_name) + '</h3>' +
      '<p>' + text(seo.description_30 || seo.catch_copy) + '</p>' +
      '<div class="catalog-meta">' +
        '<span>' + text(basic.model_number) + '</span>' +
        '<strong>' + formatYen(pricing.manufacturer_price_in_tax) + '</strong>' +
      '</div>' +
      '<a class="product-cta" href="' + detailUrl(product.id) + '">商品ページへ</a>';
    return article;
  }

  function render(products) {
    var productsById = productMap(products);
    renderHero();
    sceneGrid.textContent = '';
    SCENES.forEach(function (scene) {
      sceneGrid.appendChild(createSceneCard(scene, productsById));
    });

    catalogGrid.textContent = '';
    products.forEach(function (product) {
      catalogGrid.appendChild(createCatalogCard(product));
    });

    loadStatus.textContent = 'Garden Livingのシーンを表示しました。';
    window.setTimeout(function () {
      loadStatus.classList.add('is-hidden');
    }, 1600);
  }

  loadProducts()
    .then(function (data) {
      render(Array.isArray(data.products) ? data.products : []);
      console.info('[Garden Living] loaded products:', Array.isArray(data.products) ? data.products.length : 0);
    })
    .catch(function (error) {
      renderHero();
      if (loadStatus) {
        loadStatus.textContent = '商品マスタを読み込めませんでした。ローカル確認時は簡易サーバーで開いてください。';
      }
      console.error('[Garden Living] product load failed', error);
    });
})();
