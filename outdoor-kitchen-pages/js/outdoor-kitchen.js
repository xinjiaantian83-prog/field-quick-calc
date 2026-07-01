(function () {
  'use strict';

  var sceneGrid = document.getElementById('scene-grid');
  var catalogGrid = document.getElementById('catalog-grid');
  var loadStatus = document.getElementById('load-status');
  var heroVisual = document.getElementById('hero-visual');
  var heroCarousel = document.getElementById('hero-carousel');
  var DETAIL_PAGE = 'outdoor-kitchen-detail.html';
  var DATA_SOURCES = [
    'json/products.json',
    'products/products.json',
  ];
  var DEFAULT_HERO = {
    url: 'images/lifestyle/hero-evening-garden-pizza.jpg',
    mobileUrl: 'images/lifestyle/hero-evening-garden-pizza-mobile.jpg',
    label: '夕暮れの庭で家族とピザ窯を囲むGarden Living',
  };
  var DEFAULT_CATEGORIES = [
    'OUTDOOR COOKING',
    'DOG GARDEN',
    'OUTDOOR SAUNA',
    'GARDEN FURNITURE',
    'GARDEN ITEMS',
    'DIY SUPPORT',
  ];

  function formatYen(value) {
    if (typeof value !== 'number' || !isFinite(value)) {
      return '価格はお問い合わせください';
    }
    return '¥' + value.toLocaleString('ja-JP') + '（税込）';
  }

  function formatSize(size) {
    if (!size || typeof size !== 'object') return '仕様はお問い合わせください';
    var parts = [];
    if (typeof size.width_mm === 'number') parts.push('W' + size.width_mm);
    if (typeof size.depth_mm === 'number') parts.push('D' + size.depth_mm);
    if (typeof size.height_mm === 'number') parts.push('H' + size.height_mm);
    return parts.length ? parts.join(' x ') + 'mm' : '仕様はお問い合わせください';
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
    return 'garden-products/' + encodeURIComponent(productId) + '.html';
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

  function siteConfig(data) {
    return (data && data.garden_living) || {};
  }

  function productGarden(product) {
    return (product && product.garden_living) || {};
  }

  function productIsPublished(product) {
    var gl = productGarden(product);
    var basic = product.basic || {};
    return gl.publish !== false && basic.status !== '廃番';
  }

  function sceneFromProduct(product) {
    var gl = productGarden(product);
    var scene = gl.scene || {};
    if (!scene.id || !scene.image || gl.publish === false) return null;
    return {
      id: scene.id,
      category: scene.category || ((product.basic || {}).category || 'GARDEN LIVING'),
      title: scene.title || ((product.seo || {}).catch_copy || (product.basic || {}).product_name),
      copy: scene.copy || ((product.seo || {}).description_100 || ''),
      quote: scene.quote || '「今日は外で過ごそう。」',
      image: scene.image,
      mobileImage: scene.mobile_image || scene.mobileImage || '',
      productIds: scene.product_ids || scene.productIds || [product.id],
      detailProductId: product.id,
      status: 'available',
      order: typeof scene.order === 'number' ? scene.order : 999,
    };
  }

  function buildScenes(products, config) {
    var scenes = products
      .map(sceneFromProduct)
      .filter(Boolean)
      .sort(function (a, b) { return a.order - b.order; });
    var planned = Array.isArray(config.planned_scenes) ? config.planned_scenes : [];
    return scenes.concat(planned.map(function (scene, index) {
      return {
        id: scene.id || ('planned-' + index),
        category: scene.category || 'Garden Living',
        title: scene.title || '準備中のシーン',
        copy: scene.copy || '掲載準備が整い次第、追加します。',
        quote: scene.quote || '「次は何をしよう。」',
        image: scene.image || DEFAULT_HERO.url,
        mobileImage: scene.mobile_image || '',
        productIds: scene.product_ids || [],
        status: 'coming',
        order: typeof scene.order === 'number' ? scene.order : 999,
      };
    }));
  }

  function renderHero(config) {
    if (!heroVisual || !heroCarousel) return;
    var hero = (config && config.hero) || DEFAULT_HERO;
    heroCarousel.textContent = '';
    heroVisual.classList.remove('is-loading');
    heroVisual.classList.add('has-images');
    heroCarousel.innerHTML =
      '<figure class="hero-slide is-active">' +
        '<picture>' +
          '<source media="(max-width: 720px)" srcset="' + (hero.mobile_url || hero.mobileUrl || hero.url) + '">' +
          '<img src="' + hero.url + '" alt="' + text(hero.label) + '">' +
        '</picture>' +
        '<figcaption>' + text(hero.label) + '</figcaption>' +
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
    var gl = productGarden(product);
    var indexCopy = gl.index_copy || seo.description_30 || seo.catch_copy;
    var article = document.createElement('article');
    article.className = 'catalog-card';
    article.innerHTML =
      '<p class="product-model">' + text(basic.category) + '</p>' +
      '<h3>' + text(basic.product_name) + '</h3>' +
      '<p>' + text(indexCopy) + '</p>' +
      '<div class="catalog-specs">' +
        '<span>サイズ/仕様</span>' +
        '<strong>' + formatSize(product.size) + '</strong>' +
        '<span>メーカー</span>' +
        '<strong>' + text(basic.manufacturer) + '</strong>' +
      '</div>' +
      '<div class="catalog-meta">' +
        '<span>' + text(basic.model_number) + '</span>' +
        '<strong>' + formatYen(pricing.manufacturer_price_in_tax) + '</strong>' +
      '</div>' +
      '<div class="catalog-actions">' +
        '<a class="product-cta" href="' + detailUrl(product.id) + '">商品ページへ</a>' +
        '<a class="product-consult" href="#contact">この商品について相談する</a>' +
      '</div>';
    return article;
  }

  function render(data) {
    var config = siteConfig(data);
    var products = (Array.isArray(data.products) ? data.products : []).filter(productIsPublished);
    var productsById = productMap(products);
    var scenes = buildScenes(products, config);
    var categories = Array.isArray(config.categories) && config.categories.length ? config.categories : DEFAULT_CATEGORIES;
    renderHero(config);
    sceneGrid.textContent = '';
    scenes.forEach(function (scene) {
      sceneGrid.appendChild(createSceneCard(scene, productsById));
    });

    catalogGrid.textContent = '';
    products.forEach(function (product) {
      catalogGrid.appendChild(createCatalogCard(product));
    });

    var strip = document.querySelector('.category-strip');
    if (strip) {
      strip.innerHTML = categories.map(function (category) {
        return '<span>' + text(category) + '</span>';
      }).join('');
    }

    loadStatus.textContent = 'シーンを読み込みました。';
    window.setTimeout(function () {
      loadStatus.classList.add('is-hidden');
    }, 1600);
  }

  loadProducts()
    .then(function (data) {
      render(data || {});
      console.info('[Garden Living] loaded products:', Array.isArray(data.products) ? data.products.length : 0);
    })
    .catch(function (error) {
      renderHero({});
      if (loadStatus) {
        loadStatus.textContent = '商品マスタを読み込めませんでした。ローカル確認時は簡易サーバーで開いてください。';
      }
      console.error('[Garden Living] product load failed', error);
    });
})();
