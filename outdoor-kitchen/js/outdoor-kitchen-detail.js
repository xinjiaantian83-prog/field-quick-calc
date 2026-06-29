(function () {
  'use strict';

  var DATA_SOURCES = [
    'products/products.json',
    'json/products.json',
  ];
  var LIFESTYLE_IMAGES = {
    'eg3-ab-pk': {
      url: 'images/lifestyle/hero-evening-garden-pizza.jpg',
      label: '夕暮れの庭で家族とピザ窯を囲むGarden Living',
      sceneTitle: '夕暮れ、庭でピザを焼く。',
      sceneCopy: '火を見ながら焼き上がりを待つ時間まで、家族の思い出になります。商品からではなく、こんな時間を過ごしたいという気持ちから庭を考えます。',
      quote: '「じぃじ、またピザ作ろう！」',
    },
    'eg3-ab-bq': {
      url: 'images/lifestyle/g19-pizza-fire-table.jpg',
      label: '火と食事を囲むアウトドア調理のイメージ',
      sceneTitle: '今日は外で食べようか。',
      sceneCopy: '焼くだけではなく、集まるきっかけまでつくる庭のBBQシーン。火と料理があると、庭は自然と人が集まる場所になります。',
      quote: '「またみんなで集まろう。」',
    },
    'eg3-ab-kk': {
      url: 'images/lifestyle/g19-fire-pan-deck.jpg',
      label: '庭で火を楽しむ休日のイメージ',
      sceneTitle: '待つ時間を楽しむ、燻製の庭。',
      sceneCopy: 'すぐに食べるだけではない、香りと会話がゆっくり育つ休日。庭で過ごす時間に、少しだけ贅沢な余白をつくります。',
      quote: '「次は何を燻そうか。」',
    },
  };

  function text(value) {
    return value === null || value === undefined || value === '' ? '未確認' : String(value);
  }

  function isKnownUrl(value) {
    return typeof value === 'string' && value && value !== '未確認';
  }

  function formatYen(value) {
    if (typeof value !== 'number' || !isFinite(value)) {
      return '価格はお問い合わせください';
    }
    return value.toLocaleString('ja-JP') + '円';
  }

  function formatSceneYen(value) {
    if (typeof value !== 'number' || !isFinite(value)) {
      return '価格はお問い合わせください';
    }
    return '¥' + value.toLocaleString('ja-JP') + '（税込）';
  }

  function formatSize(size) {
    if (!size) return '未確認';
    var width = size.width_mm || '未確認';
    var depth = size.depth_mm || '未確認';
    var height = size.height_mm || '未確認';
    return 'W' + width + '×D' + depth + '×H' + height + 'mm';
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

  function getProductImages(product) {
    var photos = product.photos || {};
    var gallery = Array.isArray(photos.gallery) ? photos.gallery : [];
    var urls = gallery
      .map(function (item) { return item && item.url; })
      .filter(isKnownUrl);
    if (photos.main && isKnownUrl(photos.main.url)) {
      urls.unshift(photos.main.url);
    }
    return urls.filter(function (url, index, array) {
      return array.indexOf(url) === index;
    });
  }

  function getQueryId() {
    return new URLSearchParams(window.location.search).get('id');
  }

  function setText(id, value) {
    var el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  function createSpecRow(label, value) {
    return '<div><dt>' + label + '</dt><dd>' + text(value) + '</dd></div>';
  }

  function renderGallery(product) {
    var gallery = document.getElementById('detail-gallery');
    if (!gallery) return;
    var images = getProductImages(product);
    gallery.textContent = '';
    if (!images.length) {
      gallery.innerHTML = '<div class="product-placeholder"><span>商品写真<br>未確認</span></div>';
      return;
    }
    images.forEach(function (url, index) {
      var figure = document.createElement('figure');
      figure.className = 'detail-photo';
      figure.innerHTML = '<img src="' + url + '" alt="' + text(product.basic && product.basic.product_name) + ' 商品写真 ' + (index + 1) + '" loading="lazy">';
      gallery.appendChild(figure);
    });
  }

  function renderUsedProduct(product) {
    var area = document.getElementById('detail-used-products');
    if (!area) return;
    var basic = product.basic || {};
    var pricing = product.pricing || {};
    area.innerHTML =
      '<article class="catalog-card">' +
        '<p class="product-model">' + text(basic.manufacturer) + '</p>' +
        '<h3>' + text(basic.product_name) + '</h3>' +
        '<p>この空間で使用している商品です。仕様や設置条件は下部で確認できます。</p>' +
        '<div class="catalog-meta">' +
          '<span>' + text(basic.model_number) + '</span>' +
          '<strong>' + formatSceneYen(pricing.manufacturer_price_in_tax) + '</strong>' +
        '</div>' +
        '<a class="product-cta" href="#detail-specs">商品詳細を見る</a>' +
      '</article>';
  }

  function renderInfo(product) {
    var info = document.getElementById('detail-info');
    if (!info) return;
    var installation = product.installation || {};
    var materials = product.materials || {};
    var accessories = product.accessories || {};
    info.innerHTML =
      '<article class="info-card"><h3>材質</h3><p>本体：' + text(materials.body) + '<br>扉：' + text(materials.door) + '<br>耐火材：' + text(materials.refractory_material) + '</p></article>' +
      '<article class="info-card"><h3>付属品</h3><p>' + (Array.isArray(accessories.standard) ? accessories.standard.map(text).join('、') : text(accessories.standard)) + '</p></article>' +
      '<article class="info-card"><h3>設置方法</h3><p>' + text(installation.installation_method) + '</p></article>' +
      '<article class="info-card"><h3>推奨設置場所</h3><p>' + text(installation.recommended_location) + '</p></article>';
  }

  function renderWarnings(product) {
    var list = document.getElementById('detail-warnings');
    if (!list) return;
    var warnings = product.warnings || {};
    var items = [
      ['煙', warnings.smoke],
      ['灰', warnings.ash],
      ['火気', warnings.fire],
      ['重量', warnings.weight],
      ['可燃物', warnings.combustibles],
      ['メンテナンス', warnings.maintenance],
    ];
    list.innerHTML = items.map(function (item) {
      return '<li><strong>' + item[0] + '</strong><span>' + text(item[1]) + '</span></li>';
    }).join('');
  }

  function renderProduct(product) {
    var basic = product.basic || {};
    var pricing = product.pricing || {};
    var seo = product.seo || {};
    var docs = product.documents || {};
    var lifestyle = LIFESTYLE_IMAGES[product.id] || { url: 'images/lifestyle/g19-ooya-stone-garden.jpg', label: '庭時間の施工イメージ' };

    document.title = text(basic.product_name) + '｜Garden Living by EXた組';
    setText('detail-category', 'Garden Living / ' + text(basic.category));
    setText('detail-title', text(basic.product_name));
    setText('detail-lead', text(lifestyle.sceneCopy || seo.description_100 || seo.catch_copy));
    setText('detail-scene-title', text(lifestyle.sceneTitle || 'この空間で過ごす時間'));
    setText('detail-scene-copy', text(lifestyle.sceneCopy || seo.description_100 || seo.catch_copy));
    setText('detail-scene-quote', text(lifestyle.quote || '「今日は外で食べようか。」'));
    setText('detail-model', text(basic.model_number));

    var heroImage = document.getElementById('detail-hero-image');
    if (heroImage) {
      heroImage.innerHTML = '<img src="' + lifestyle.url + '" alt="' + lifestyle.label + '">';
    }

    renderUsedProduct(product);
    var specs = document.getElementById('detail-specs');
    if (specs) {
      specs.innerHTML =
        createSpecRow('型番', basic.model_number) +
        createSpecRow('メーカー', basic.manufacturer) +
        createSpecRow('シリーズ', basic.series) +
        createSpecRow('サイズ', formatSize(product.size)) +
        createSpecRow('税込定価', formatYen(pricing.manufacturer_price_in_tax)) +
        createSpecRow('寸法図', docs.dimension_drawing || '未確認');
    }

    renderGallery(product);
    renderInfo(product);
    renderWarnings(product);
  }

  loadProducts()
    .then(function (data) {
      var products = Array.isArray(data.products) ? data.products : [];
      var id = getQueryId();
      var product = products.find(function (item) { return item.id === id; }) || products[0];
      if (!product) throw new Error('product not found');
      renderProduct(product);
      console.info('[Outdoor Kitchen Detail] loaded:', product.id);
    })
    .catch(function (error) {
      setText('detail-title', '商品情報を読み込めませんでした。');
      setText('detail-lead', 'ローカル確認時は簡易サーバーで開いてください。');
      console.error('[Outdoor Kitchen Detail] load failed', error);
    });
})();
