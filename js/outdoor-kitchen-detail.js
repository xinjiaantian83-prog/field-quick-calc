(function () {
  'use strict';

  var PRODUCT_SOURCES = ['json/products.json', '../json/products.json', 'products/products.json'];
  var G20_SOURCES = ['json/g20-material-candidates.json', '../json/g20-material-candidates.json'];
  var DEFAULT_IMAGE = 'images/lifestyle/hero-evening-garden-pizza.jpg';
  var LINE_URL = 'https://line.me/R/ti/p/@953wnidc';
  var STORAGE_KEY = 'garden_living_saved_products_v1';

  function text(value) {
    return value === null || value === undefined || value === '' ? '未確認' : String(value);
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
    var unique = ids.filter(function (id, index, array) {
      return id && array.indexOf(id) === index;
    });
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(unique));
    return unique;
  }

  function isSaved(productId) {
    return readSavedIds().indexOf(String(productId)) !== -1;
  }

  function productParams(product) {
    return {
      product_id: product.id,
      product_name: product.name,
      category: product.category,
      maker: product.maker,
    };
  }

  function assetUrl(url) {
    if (!url || url === '未確認') return url;
    if (/^(https?:)?\/\//.test(url) || url.charAt(0) === '/') return url;
    return window.location.pathname.indexOf('/garden-products/') !== -1 ? '../' + url : url;
  }

  function formatYen(value) {
    if (typeof value !== 'number' || !isFinite(value) || value <= 0) return '相談価格';
    return '¥' + value.toLocaleString('ja-JP') + '（税込）';
  }

  function formatPublicPrice(value) {
    if (typeof value !== 'number' || !isFinite(value) || value <= 0) return '相談価格';
    return 'EXた組価格 ' + formatYen(value);
  }

  function publicPrice(product) {
    return product.priceLabel || formatPublicPrice(product.price);
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

  function getQueryId() {
    return window.GARDEN_LIVING_PRODUCT_ID || new URLSearchParams(window.location.search).get('id');
  }

  function setText(id, value) {
    var el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  function createSpecRow(label, value) {
    return '<div><dt>' + label + '</dt><dd>' + text(value) + '</dd></div>';
  }

  function formatOldSize(product) {
    var size = product.size || {};
    var width = size.width_mm || '未確認';
    var depth = size.depth_mm || '未確認';
    var height = size.height_mm || '未確認';
    return 'W' + width + '×D' + depth + '×H' + height + 'mm';
  }

  function getOldImage(product) {
    var photos = product.photos || {};
    if (photos.main && photos.main.url) return assetUrl(photos.main.url);
    var gallery = Array.isArray(photos.gallery) ? photos.gallery : [];
    var first = gallery.find(function (item) { return item && item.url; });
    var scene = product.garden_living && product.garden_living.scene;
    return assetUrl((first && first.url) || (scene && scene.image) || DEFAULT_IMAGE);
  }

  function convertOldProduct(product) {
    var basic = product.basic || {};
    var seo = product.seo || {};
    var pricing = product.pricing || {};
    var installation = product.installation || {};
    var materials = product.materials || {};
    var accessories = product.accessories || {};
    return {
      id: product.id,
      name: text(basic.product_name),
      model: text(basic.model_number),
      category: g20Category(basic.category),
      maker: text(basic.manufacturer || 'OnlyOneClub'),
      image: getOldImage(product),
      description: text(seo.description_300 || seo.description_100 || seo.catch_copy),
      size: formatOldSize(product),
      colors: [],
      install: text(installation.installation_method),
      price: pricing.extakumi_price || null,
      priceLabel: '',
      material: text(materials.body),
      accessories: Array.isArray(accessories.standard) ? accessories.standard.map(text).join('、') : text(accessories.standard),
      rakutenUrl: '',
      yahooUrl: '',
      amazonUrl: '',
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
    return value || 'その他';
  }

  function g20Image(product) {
    var file = product.image_file_name || product.product_image || product.image;
    if (!file || file === '未確認') return assetUrl(DEFAULT_IMAGE);
    if (/^(https?:)?\/\//.test(file) || file.charAt(0) === '/') return file;
    if (file.indexOf('/') !== -1) return assetUrl('images/g20-material/' + file.replace(/^images\/g20-material\//, ''));
    return assetUrl('images/g20-material/' + file);
  }

  function searchUrl(source, product) {
    var query = encodeURIComponent([product.model, product.name].filter(Boolean).join(' '));
    if (source === 'rakuten') return product.rakutenUrl || 'https://search.rakuten.co.jp/search/mall/' + query + '/';
    if (source === 'yahoo') return product.yahooUrl || 'https://shopping.yahoo.co.jp/search?p=' + query;
    return product.amazonUrl || 'https://www.amazon.co.jp/s?k=' + query;
  }

  function convertG20Product(product) {
    return {
      id: product.product_id,
      name: text(product.product_name),
      model: text(product.model_number || product.representative_product_code),
      category: g20Category(product.category),
      maker: text(product.manufacturer || 'OnlyOneClub'),
      image: g20Image(product),
      description: text(product.comment || product.series_name || '庭まわりで使うセレクト商品です。'),
      size: text(product.size_label || product.size),
      colors: Array.isArray(product.colors) ? product.colors : [],
      install: text(product.install_type),
      price: product.extakumi_price || null,
      priceLabel: product.extakumi_price_label || '',
      material: text(product.material || product.materials),
      accessories: '未確認',
      rakutenUrl: product.rakuten_url || (product.compare_links && product.compare_links.rakuten) || '',
      yahooUrl: product.yahoo_url || (product.compare_links && product.compare_links.yahoo) || '',
      amazonUrl: product.amazon_url || (product.compare_links && product.compare_links.amazon) || '',
    };
  }

  function renderGallery(product) {
    var gallery = document.getElementById('detail-gallery');
    if (!gallery) return;
    gallery.innerHTML =
      '<figure class="detail-photo"><img src="' + product.image + '" alt="' + product.name + '" loading="lazy"></figure>';
  }

  function renderCompare(product) {
    var area = document.getElementById('detail-compare');
    if (!area) return;
    area.innerHTML =
      '<a class="compare-btn js-compare-track" href="' + searchUrl('rakuten', product) + '" target="_blank" rel="noopener noreferrer" data-compare-site="rakuten">楽天で見る</a>' +
      '<a class="compare-btn js-compare-track" href="' + searchUrl('yahoo', product) + '" target="_blank" rel="noopener noreferrer" data-compare-site="yahoo">Yahoo!で見る</a>' +
      '<a class="compare-btn js-compare-track" href="' + searchUrl('amazon', product) + '" target="_blank" rel="noopener noreferrer" data-compare-site="amazon">Amazonで見る</a>';
  }

  function updateFavoriteButton(product) {
    var button = document.getElementById('detail-favorite');
    if (!button) return;
    var saved = isSaved(product.id);
    button.textContent = saved ? '♥ 保存済み' : '♡ 気になる';
    button.setAttribute('aria-pressed', saved ? 'true' : 'false');
  }

  function bindDetailActions(product) {
    var favoriteButton = document.getElementById('detail-favorite');
    if (favoriteButton) {
      favoriteButton.addEventListener('click', function () {
        var ids = readSavedIds();
        if (ids.indexOf(product.id) !== -1) {
          writeSavedIds(ids.filter(function (id) { return id !== product.id; }));
          track('gl_product_unlike', productParams(product));
        } else {
          writeSavedIds(ids.concat(product.id));
          track('gl_product_like', productParams(product));
        }
        updateFavoriteButton(product);
      });
    }

    document.querySelectorAll('.js-compare-track').forEach(function (link) {
      link.addEventListener('click', function () {
        var params = productParams(product);
        params.compare_site = link.dataset.compareSite || 'unknown';
        track('gl_compare_click', params);
      });
    });

    ['detail-line-link', 'detail-contact-line-link'].forEach(function (id) {
      var link = document.getElementById(id);
      if (!link) return;
      link.addEventListener('click', function () {
        var params = productParams(product);
        params.source = 'product_detail';
        track('gl_line_click', params);
      });
    });
  }

  function renderInfo(product) {
    var info = document.getElementById('detail-info');
    if (!info) return;
    info.innerHTML =
      '<article class="info-card"><h3>商品説明</h3><p>' + product.description + '</p></article>' +
      '<article class="info-card"><h3>カラー</h3><p>' + (product.colors.length ? product.colors.map(text).join('、') : '未確認') + '</p></article>' +
      '<article class="info-card"><h3>材質</h3><p>' + text(product.material) + '</p></article>' +
      '<article class="info-card"><h3>付属品</h3><p>' + text(product.accessories) + '</p></article>';
  }

  function renderProduct(product) {
    document.title = product.name + '｜Garden Living by EXた組';
    setText('detail-category', 'Garden Living / ' + product.category);
    setText('detail-title', product.name);
    setText('detail-lead', product.description);
    setText('detail-model', product.model);

    var heroImage = document.getElementById('detail-hero-image');
    if (heroImage) heroImage.innerHTML = '<img src="' + product.image + '" alt="' + product.name + '">';

    var specs = document.getElementById('detail-specs');
    if (specs) {
      specs.innerHTML =
        createSpecRow('メーカー', product.maker) +
        createSpecRow('品番', product.model) +
        createSpecRow('カテゴリ', product.category) +
        createSpecRow('サイズ', product.size) +
        createSpecRow('カラー', product.colors.length ? product.colors.join('、') : '未確認') +
        createSpecRow('施工方法', product.install) +
        createSpecRow('価格', publicPrice(product));
    }

    var line = document.getElementById('detail-line-link');
    if (line) line.href = LINE_URL;
    var contactLine = document.getElementById('detail-contact-line-link');
    if (contactLine) contactLine.href = LINE_URL;

    renderGallery(product);
    renderInfo(product);
    renderCompare(product);
    updateFavoriteButton(product);
    bindDetailActions(product);
    track('gl_product_view', productParams(product));
  }

  Promise.allSettled([loadJson(PRODUCT_SOURCES), loadJson(G20_SOURCES)])
    .then(function (results) {
      var oldData = results[0].status === 'fulfilled' ? results[0].value : {};
      var g20Data = results[1].status === 'fulfilled' ? results[1].value : {};
      var oldProducts = (Array.isArray(oldData.products) ? oldData.products : []).map(convertOldProduct);
      var g20Products = (Array.isArray(g20Data.products) ? g20Data.products : []).map(convertG20Product);
      var products = oldProducts.concat(g20Products);
      var id = getQueryId();
      var product = products.find(function (item) { return item.id === id; }) || products[0];
      if (!product) throw new Error('product not found');
      renderProduct(product);
      console.info('[Garden Living Detail] loaded:', product.id);
    })
    .catch(function (error) {
      setText('detail-title', '商品情報を読み込めませんでした。');
      setText('detail-lead', 'ローカル確認時は簡易サーバーで開いてください。');
      console.error('[Garden Living Detail] load failed', error);
    });
})();
