(function () {
  'use strict';

  var catalogGrid = document.getElementById('catalog-grid');
  var newGrid = document.getElementById('new-grid');
  var popularGrid = document.getElementById('popular-grid');
  var categoryGrid = document.getElementById('category-grid');
  var makerGrid = document.getElementById('maker-grid');
  var loadStatus = document.getElementById('load-status');
  var searchInput = document.getElementById('product-search');
  var clearFilter = document.getElementById('clear-filter');
  var savedFilter = document.getElementById('saved-filter');
  var savedCount = document.getElementById('saved-count');
  var resultCount = document.getElementById('result-count');
  var heroVisual = document.getElementById('hero-visual');

  var PRODUCT_SOURCES = ['json/products.json', 'products/products.json'];
  var G20_SOURCES = ['json/g20-material-candidates.json'];
  var TARGET_CATEGORIES = [
    '車止め',
    'サイクルスタンド',
    'アメリカンフェンス',
    '機能門柱',
    '宅配ボックス',
    'ポスト',
    'ガビオン',
    '立水栓',
    '人工芝',
    '防草シート',
    'ピザ窯',
  ];
  var LINE_URL = 'https://line.me/R/ti/p/@953wnidc';
  var CATEGORY_META = {
    '車止め': '愛車を美しく守るデザイン車止め',
    'サイクルスタンド': '自転車置き場をすっきり整えるスタンド',
    'アメリカンフェンス': '庭に抜け感をつくるラフなフェンス',
    '機能門柱': '玄関を彩るデザイン門柱',
    '宅配ボックス': '不在時も安心。',
    'ポスト': '毎日使うものだから、こだわりたい。',
    'ガビオン': '庭を彩るストーンウォール',
    '立水栓': '庭の使い勝手をもっと快適に。',
    '人工芝': '一年中美しい緑。',
    '防草シート': '雑草対策をプロ仕様で。',
    'ピザ窯': '庭で過ごす時間をもっと楽しく。',
  };
  var CATEGORY_VISUALS = {
    '車止め': 'images/g20-material/carstop-flute-six.webp',
    'サイクルスタンド': 'images/g20-material/cycle-stand-type-a-fixed-stainless.jpg',
    'アメリカンフェンス': 'images/lifestyle/categories/category-american-fence.png',
    '機能門柱': 'images/g20-material/function-post/gm1-aon-a-b.jpg',
    '宅配ボックス': 'images/g20-material/delivery-box/koln-double-a-slate-black-left.jpg',
    'ポスト': 'images/g20-material/post/macaron-one-stand-matte-black.jpg',
    'ガビオン': 'images/lifestyle/categories/category-gabion.jpg',
    '立水栓': 'images/lifestyle/categories/category-water-stand.png',
    '人工芝': 'images/lifestyle/garden-living-hero-final-photo.png',
    '防草シート': 'images/g20-material/weed-sheet/nax-ex-weed-sheet-product.jpg',
    'ピザ窯': 'images/lifestyle/hero-evening-garden-pizza.jpg',
  };
  var MAKERS = ['OnlyOneClub', 'LIXIL', 'YKK AP', '三協アルミ', '四国化成', 'タカショー', 'ユニソン'];
  var DEFAULT_IMAGE = 'images/lifestyle/hero-evening-garden-pizza.jpg';
  var HERO_IMAGE = 'images/lifestyle/garden-living-hero-final-photo.png';
  var STORAGE_KEY = 'garden_living_saved_products_v1';

  var state = {
    products: [],
    activeCategory: 'すべて',
    query: '',
    showSaved: false,
    showCatalog: false,
    savedIds: [],
  };

  function text(value) {
    return value === null || value === undefined || value === '' ? '未確認' : String(value);
  }

  function normalize(value) {
    return text(value).toLowerCase();
  }

  function escapeHtml(value) {
    return text(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function track(eventName, params) {
    if (window.gtag) {
      window.gtag('event', eventName, params || {});
    }
  }

  function readSavedIds() {
    try {
      var parsed = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || '[]');
      return Array.isArray(parsed) ? parsed.filter(Boolean).map(String) : [];
    } catch (error) {
      return [];
    }
  }

  function writeSavedIds(ids) {
    state.savedIds = ids.filter(function (id, index, array) {
      return id && array.indexOf(id) === index;
    });
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state.savedIds));
    updateSavedCount();
  }

  function isSaved(productId) {
    return state.savedIds.indexOf(String(productId)) !== -1;
  }

  function productParams(product) {
    return {
      product_id: product.id,
      product_name: product.name,
      category: product.category,
      maker: product.maker,
    };
  }

  function updateSavedCount() {
    if (savedCount) savedCount.textContent = String(state.savedIds.length);
    if (savedFilter) {
      savedFilter.classList.toggle('is-active', state.showSaved);
      savedFilter.setAttribute('aria-pressed', state.showSaved ? 'true' : 'false');
    }
  }

  function formatYen(value) {
    if (typeof value !== 'number' || !isFinite(value) || value <= 0) {
      return '相談価格';
    }
    return '¥' + value.toLocaleString('ja-JP') + '（税込）';
  }

  function formatPublicPrice(value, label) {
    if (label) return label;
    if (typeof value !== 'number' || !isFinite(value) || value <= 0) return '相談価格';
    return 'EXた組価格 ' + formatYen(value);
  }

  function loadJson(sources) {
    return sources.reduce(function (promise, source) {
      return promise.catch(function () {
        return fetch(source, { cache: 'no-store' }).then(function (response) {
          if (!response.ok) throw new Error(source + ' load failed');
          return response.json();
        });
      });
    }, Promise.reject());
  }

  function oldProductIsPublished(product) {
    var gl = product.garden_living || {};
    var basic = product.basic || {};
    return gl.publish !== false && basic.status !== '廃番';
  }

  function oldProductImage(product) {
    var photos = product.photos || {};
    if (photos.main && photos.main.url) return photos.main.url;
    var gallery = Array.isArray(photos.gallery) ? photos.gallery : [];
    var first = gallery.find(function (item) { return item && item.url; });
    var scene = product.garden_living && product.garden_living.scene;
    return (first && first.url) || (scene && scene.image) || DEFAULT_IMAGE;
  }

  function formatOldSize(product) {
    var size = product.size || {};
    var parts = [];
    if (size.width_mm) parts.push('W' + size.width_mm);
    if (size.depth_mm) parts.push('D' + size.depth_mm);
    if (size.height_mm) parts.push('H' + size.height_mm);
    return parts.length ? parts.join(' × ') + 'mm' : '仕様はお問い合わせください';
  }

  function convertOldProduct(product, index) {
    var basic = product.basic || {};
    var seo = product.seo || {};
    var pricing = product.pricing || {};
    return {
      id: product.id,
      source: 'products',
      name: text(basic.product_name),
      model: text(basic.model_number),
      category: g20Category(basic.category || 'その他'),
      maker: text(basic.manufacturer || 'OnlyOneClub'),
      image: oldProductImage(product),
      price: pricing.extakumi_price || null,
      priceLabel: '',
      description: text(seo.description_100 || seo.catch_copy || (product.garden_living && product.garden_living.index_copy) || ''),
      size: formatOldSize(product),
      colors: [],
      install: text(product.installation && product.installation.installation_method),
      priority: 80,
      order: index,
      detailUrl: 'garden-products/' + encodeURIComponent(product.id) + '.html',
    };
  }

  function g20Category(category) {
    var value = text(category);
    if (value.indexOf('車止め') !== -1 || value.indexOf('カーストッパー') !== -1) return '車止め';
    if (value.indexOf('サイクル') !== -1) return 'サイクルスタンド';
    if (value.indexOf('アメリカンフェンス') !== -1) return 'アメリカンフェンス';
    if (value.indexOf('機能門柱') !== -1) return '機能門柱';
    if (value.indexOf('宅配') !== -1) return '宅配ボックス';
    if (value.indexOf('ポスト') !== -1) return 'ポスト';
    if (value.indexOf('ガビオン') !== -1) return 'ガビオン';
    if (value.indexOf('立水栓') !== -1 || value.indexOf('水栓') !== -1 || value.indexOf('ガーデンシンク') !== -1) return '立水栓';
    if (value.indexOf('人工芝') !== -1 || value.indexOf('芝') !== -1) return '人工芝';
    if (value.indexOf('防草') !== -1) return '防草シート';
    if (value.indexOf('ピザ') !== -1 || value.indexOf('BBQ') !== -1 || value.indexOf('バーベキュー') !== -1 || value.indexOf('燻製') !== -1) return 'ピザ窯';
    return TARGET_CATEGORIES.indexOf(value) !== -1 ? value : 'その他';
  }

  function g20Image(product) {
    var file = product.image_file_name || product.product_image || product.image;
    if (!file || file === '未確認') return DEFAULT_IMAGE;
    if (/^(https?:)?\/\//.test(file) || file.charAt(0) === '/') return file;
    if (file.indexOf('/') !== -1) return 'images/g20-material/' + file.replace(/^images\/g20-material\//, '');
    return 'images/g20-material/' + file;
  }

  function g20Price(product) {
    return product.extakumi_price || null;
  }

  function convertG20Product(product, index) {
    var category = g20Category(product.category);
    return {
      id: product.product_id,
      source: 'g20',
      name: text(product.product_name),
      model: text(product.model_number || product.representative_product_code),
      category: category,
      maker: text(product.manufacturer || 'OnlyOneClub'),
      image: g20Image(product),
      price: g20Price(product),
      priceLabel: product.extakumi_price_label || '',
      description: text(product.comment || product.series_name || ''),
      size: text(product.size_label || product.size),
      colors: Array.isArray(product.colors) ? product.colors : [],
      install: text(product.install_type),
      priority: product.sales_priority === 'A' ? 100 : product.sales_priority === 'B' ? 70 : 40,
      order: 10000 + index,
      detailUrl: 'outdoor-kitchen-detail.html?id=' + encodeURIComponent(product.product_id),
    };
  }

  function publishedG20(product) {
    if (!product || !product.product_id || !product.product_name) return false;
    return TARGET_CATEGORIES.indexOf(g20Category(product.category)) !== -1;
  }

  function dedupe(products) {
    var seen = {};
    return products.filter(function (product) {
      if (!product.id || seen[product.id]) return false;
      seen[product.id] = true;
      return true;
    });
  }

  function productSearchText(product) {
    return [
      product.id,
      product.name,
      product.model,
      product.category,
      product.maker,
      product.size,
      product.install,
      product.colors.join(' '),
    ].map(normalize).join(' ');
  }

  function filteredProducts() {
    return state.products.filter(function (product) {
      var savedOk = !state.showSaved || isSaved(product.id);
      var categoryOk = state.showSaved || state.activeCategory === 'すべて' || product.category === state.activeCategory;
      var queryOk = !state.query || productSearchText(product).indexOf(normalize(state.query)) !== -1;
      return savedOk && categoryOk && queryOk;
    });
  }

  function createCard(product) {
    var saved = isSaved(product.id);
    var lineSource = state.showSaved ? 'saved_list' : 'product_card';
    var article = document.createElement('article');
    article.className = 'shop-card';
    article.innerHTML =
      '<div class="shop-card-inner">' +
        '<figure class="shop-card-image"><img src="' + escapeHtml(product.image) + '" alt="' + escapeHtml(product.name) + '" loading="lazy"></figure>' +
        '<div class="shop-card-body">' +
          '<p class="product-model">' + escapeHtml(product.category) + '</p>' +
          '<h3>' + escapeHtml(product.name) + '</h3>' +
          '<p class="shop-card-price">' + escapeHtml(formatPublicPrice(product.price, product.priceLabel)) + '</p>' +
          '<div class="shop-card-actions">' +
            '<button class="favorite-btn js-favorite" type="button" data-product-id="' + escapeHtml(product.id) + '" aria-pressed="' + (saved ? 'true' : 'false') + '">' + (saved ? '♥ 保存済み' : '♡ 気になる') + '</button>' +
            '<a class="product-cta" href="' + escapeHtml(product.detailUrl) + '">詳細を見る</a>' +
            '<a class="product-consult js-line-track" href="' + LINE_URL + '" target="_blank" rel="noopener noreferrer" data-product-id="' + escapeHtml(product.id) + '" data-source="' + lineSource + '">LINEで相談</a>' +
          '</div>' +
        '</div>' +
      '</div>';
    return article;
  }

  function renderCards(container, products) {
    if (!container) return;
    container.textContent = '';
    if (!products.length) {
      container.innerHTML = '<p class="empty-message">該当する商品がありません。</p>';
      return;
    }
    products.forEach(function (product) {
      container.appendChild(createCard(product));
    });
  }

  function renderCatalog(list) {
    if (!catalogGrid) return;
    if (!state.showCatalog) {
      catalogGrid.innerHTML =
        '<div class="catalog-intro">' +
          '<p class="eyebrow">Select First</p>' +
          '<h3>カテゴリや検索から、必要な商品だけ表示します。</h3>' +
          '<p>トップでは商品カードを並べすぎず、庭の使い方やカテゴリを選ぶ入口として整理しています。</p>' +
        '</div>';
      if (resultCount) resultCount.textContent = 'カテゴリを選ぶか、検索すると商品一覧を表示します。';
      return;
    }
    renderCards(catalogGrid, list);
  }

  function categoryCount(category) {
    if (category === 'すべて') return state.products.length;
    return state.products.filter(function (product) { return product.category === category; }).length;
  }

  function renderCategories() {
    if (!categoryGrid) return;
    var categories = TARGET_CATEGORIES;
    categoryGrid.innerHTML = categories.map(function (category) {
      var active = state.activeCategory === category ? ' is-active' : '';
      var imageProduct = state.products.find(function (product) {
        return product.category === category && product.image && product.image !== DEFAULT_IMAGE;
      }) || state.products.find(function (product) { return product.category === category; });
      var image = CATEGORY_VISUALS[category] || (imageProduct ? imageProduct.image : DEFAULT_IMAGE);
      return '<button class="category-card category-card-large' + active + '" type="button" data-category="' + category + '">' +
        '<figure><img src="' + image + '" alt="' + category + '" loading="lazy"></figure>' +
        '<span class="category-label">Category</span>' +
        '<span class="category-name">' + category + '</span>' +
        '<small>' + (CATEGORY_META[category] || '庭まわりの商品を探せます。') + '</small>' +
        '<strong>' + categoryCount(category) + '件</strong>' +
      '</button>';
    }).join('');
    categoryGrid.querySelectorAll('button').forEach(function (button) {
      button.addEventListener('click', function () {
        state.activeCategory = button.dataset.category || 'すべて';
        state.showSaved = false;
        state.showCatalog = true;
        track('gl_category_click', {
          category: state.activeCategory,
          category_count: categoryCount(state.activeCategory),
        });
        renderAll();
        document.getElementById('catalog').scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });
  }

  function makerLabel(name) {
    return name === 'オンリーワンクラブ' ? 'OnlyOneClub' : name;
  }

  function renderMakers() {
    if (!makerGrid) return;
    makerGrid.innerHTML = MAKERS.map(function (maker) {
      var count = state.products.filter(function (product) {
        return makerLabel(product.maker) === maker;
      }).length;
      return '<button class="maker-card" type="button" data-maker="' + maker + '">' +
        '<span>' + maker + '</span><strong>' + count + '</strong>' +
      '</button>';
    }).join('');
    makerGrid.querySelectorAll('button').forEach(function (button) {
      button.addEventListener('click', function () {
        state.query = button.dataset.maker || '';
        if (searchInput) searchInput.value = state.query;
        state.activeCategory = 'すべて';
        state.showSaved = false;
        state.showCatalog = true;
        renderAll();
        document.getElementById('catalog').scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });
  }

  function renderHero() {
    if (!heroVisual) return;
    heroVisual.innerHTML =
      '<figure class="hero-lifestyle">' +
        '<img src="' + HERO_IMAGE + '" alt="アメリカンフェンスと人工芝のある庭で過ごすGarden Livingのイメージ">' +
        '<figcaption>' +
          '<strong>庭で過ごす時間から、商品を選ぶ。</strong>' +
          '<span>フェンス・人工芝・水まわり・ガーデンアイテムまで</span>' +
        '</figcaption>' +
      '</figure>';
  }

  function renderAll() {
    var list = filteredProducts();
    renderCategories();
    renderCatalog(list);
    if (resultCount) {
      if (state.showCatalog) {
        var prefix = state.showSaved ? '保存した商品 ' : state.activeCategory === 'すべて' ? '' : state.activeCategory + ' ';
        resultCount.textContent = prefix + list.length + '件の商品を表示中';
      }
    }
    if (newGrid) renderCards(newGrid, state.products.slice().sort(function (a, b) { return b.order - a.order; }).slice(0, 6));
    if (popularGrid) renderCards(popularGrid, state.products.slice().sort(function (a, b) { return b.priority - a.priority; }).slice(0, 6));
    renderMakers();
    updateSavedCount();
  }

  function bindSearch() {
    if (searchInput) {
      searchInput.addEventListener('input', function () {
        state.query = searchInput.value.trim();
        state.showSaved = false;
        state.activeCategory = 'すべて';
        state.showCatalog = state.query.length > 0;
        renderAll();
      });
    }
    if (savedFilter) {
      savedFilter.addEventListener('click', function () {
        state.showSaved = true;
        state.activeCategory = 'すべて';
        state.showCatalog = true;
        renderAll();
        track('gl_saved_list_view', { saved_count: state.savedIds.length });
        document.getElementById('catalog').scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    }
    if (clearFilter) {
      clearFilter.addEventListener('click', function () {
        state.query = '';
        state.activeCategory = 'すべて';
        state.showSaved = false;
        state.showCatalog = true;
        if (searchInput) searchInput.value = '';
        renderAll();
        document.getElementById('catalog').scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    }
  }

  function findProduct(productId) {
    return state.products.find(function (product) { return product.id === productId; });
  }

  function bindProductActions() {
    document.addEventListener('click', function (event) {
      var favoriteButton = event.target.closest('.js-favorite');
      if (favoriteButton) {
        var product = findProduct(favoriteButton.dataset.productId);
        if (!product) return;
        if (isSaved(product.id)) {
          writeSavedIds(state.savedIds.filter(function (id) { return id !== product.id; }));
          track('gl_product_unlike', productParams(product));
        } else {
          writeSavedIds(state.savedIds.concat(product.id));
          track('gl_product_like', productParams(product));
        }
        renderAll();
        return;
      }

      var sceneCategoryButton = event.target.closest('.scene-category-button');
      if (sceneCategoryButton) {
        state.activeCategory = sceneCategoryButton.dataset.category || 'すべて';
        state.showSaved = false;
        state.showCatalog = true;
        if (searchInput) {
          state.query = '';
          searchInput.value = '';
        }
        track('gl_category_click', {
          category: state.activeCategory,
          category_count: categoryCount(state.activeCategory),
        });
        renderAll();
        document.getElementById('catalog').scrollIntoView({ behavior: 'smooth', block: 'start' });
        return;
      }

      var lineLink = event.target.closest('.js-line-track');
      if (lineLink) {
        var lineProduct = findProduct(lineLink.dataset.productId);
        var params = lineProduct ? productParams(lineProduct) : {};
        params.source = lineLink.dataset.source || 'unknown';
        track('gl_line_click', params);
      }
    });
  }

  Promise.allSettled([loadJson(PRODUCT_SOURCES), loadJson(G20_SOURCES)])
    .then(function (results) {
      var oldData = results[0].status === 'fulfilled' ? results[0].value : {};
      var g20Data = results[1].status === 'fulfilled' ? results[1].value : {};
      var oldProducts = (Array.isArray(oldData.products) ? oldData.products : [])
        .filter(oldProductIsPublished)
        .map(convertOldProduct);
      var g20Products = (Array.isArray(g20Data.products) ? g20Data.products : [])
        .filter(publishedG20)
        .map(convertG20Product);
      state.savedIds = readSavedIds();
      state.products = dedupe(oldProducts.concat(g20Products));
      renderHero();
      bindSearch();
      bindProductActions();
      renderAll();
      if (loadStatus) {
        loadStatus.textContent = state.products.length + '件の商品を読み込みました。';
        window.setTimeout(function () { loadStatus.classList.add('is-hidden'); }, 1600);
      }
      console.info('[Garden Living] loaded shop products:', state.products.length);
    })
    .catch(function (error) {
      if (loadStatus) loadStatus.textContent = '商品を読み込めませんでした。';
      if (resultCount) resultCount.textContent = '商品を読み込めませんでした。';
      console.error('[Garden Living] product load failed', error);
    });
})();
