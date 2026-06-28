(function () {
  'use strict';

  var productGrid = document.getElementById('product-grid');
  var comparisonBody = document.getElementById('comparison-body');
  var loadStatus = document.getElementById('load-status');
  var heroVisual = document.getElementById('hero-visual');
  var heroCarousel = document.getElementById('hero-carousel');
  var DATA_SOURCES = [
    'products/products.json',
    'json/products.json',
  ];

  function formatYen(value) {
    if (typeof value !== 'number' || !isFinite(value)) {
      return '価格はお問い合わせください';
    }
    return value.toLocaleString('ja-JP') + '円';
  }

  function formatSize(size) {
    if (!size) return '未確認';
    var width = size.width_mm || '未確認';
    var depth = size.depth_mm || '未確認';
    var height = size.height_mm || '未確認';
    return 'W' + width + '×D' + depth + '×H' + height + 'mm';
  }

  function ratingStars(value) {
    var rating = Number(value);
    if (!rating || rating < 1) return '未確認';
    var full = Math.max(0, Math.min(5, Math.round(rating)));
    return '★★★★★'.slice(0, full) + '☆☆☆☆☆'.slice(0, 5 - full);
  }

  function text(value) {
    return value === null || value === undefined || value === '' ? '未確認' : String(value);
  }

  function isKnownUrl(value) {
    return typeof value === 'string' && value && value !== '未確認';
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

  function renderProductMedia(product, basic) {
    var images = getProductImages(product);
    if (!images.length) {
      return '<div class="product-placeholder"><span>' + text(basic.category) + '<br>画像未確認</span></div>';
    }
    return '<div class="product-media"><img src="' + images[0] + '" alt="' + text(basic.product_name) + '" loading="lazy"></div>';
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

  function createProductCard(product) {
    var basic = product.basic || {};
    var pricing = product.pricing || {};
    var seo = product.seo || {};
    var rating = product.comparison_rating || {};
    var article = document.createElement('article');
    article.className = 'product-card';
    article.innerHTML =
      renderProductMedia(product, basic) +
      '<div class="product-body">' +
        '<div class="product-meta">' +
          '<span class="chip">' + text(basic.category) + '</span>' +
          '<span class="chip">' + text(basic.model_number) + '</span>' +
        '</div>' +
        '<h3>' + text(basic.product_name) + '</h3>' +
        '<p class="product-desc">' + text(seo.description_30) + '</p>' +
        '<dl class="spec-list">' +
          '<div class="spec-row"><dt>サイズ</dt><dd>' + formatSize(product.size) + '</dd></div>' +
          '<div class="spec-row"><dt>税込定価</dt><dd>' + formatYen(pricing.manufacturer_price_in_tax) + '</dd></div>' +
          '<div class="spec-row"><dt>映え評価</dt><dd><span class="rating">' + ratingStars(rating.visual_appeal) + '</span></dd></div>' +
          '<div class="spec-row"><dt>おすすめ度</dt><dd><span class="rating">' + ratingStars(rating.recommendation) + '</span></dd></div>' +
        '</dl>' +
      '</div>';
    return article;
  }

  function createComparisonRow(product) {
    var basic = product.basic || {};
    var pricing = product.pricing || {};
    var support = product.cooking_support || {};
    var rating = product.comparison_rating || {};
    var tr = document.createElement('tr');
    tr.innerHTML =
      '<td><strong>' + text(basic.product_name) + '</strong><br><small>' + text(basic.model_number) + '</small></td>' +
      '<td>' + text(basic.category) + '</td>' +
      '<td>' + formatSize(product.size) + '</td>' +
      '<td>' + formatYen(pricing.manufacturer_price_in_tax) + '</td>' +
      '<td>' + text(support.pizza) + '</td>' +
      '<td>' + text(support.bbq) + '</td>' +
      '<td>' + text(support.smoking) + '</td>' +
      '<td><span class="rating">' + ratingStars(rating.visual_appeal) + '</span></td>' +
      '<td><span class="rating">' + ratingStars(rating.recommendation) + '</span></td>';
    return tr;
  }

  function renderHero(products) {
    if (!heroVisual || !heroCarousel) return;
    var slides = [];
    products.forEach(function (product) {
      var basic = product.basic || {};
      getProductImages(product).forEach(function (url) {
        slides.push({
          url: url,
          name: text(basic.product_name),
        });
      });
    });

    heroCarousel.textContent = '';
    if (!slides.length) {
      heroVisual.classList.remove('has-images');
      heroVisual.classList.add('is-loading');
      heroCarousel.innerHTML = '<div class="hero-placeholder">画像未確認</div>';
      return;
    }

    heroVisual.classList.remove('is-loading');
    heroVisual.classList.add('has-images');
    slides.forEach(function (slide, index) {
      var figure = document.createElement('figure');
      figure.className = 'hero-slide' + (index === 0 ? ' is-active' : '');
      figure.innerHTML = '<img src="' + slide.url + '" alt="' + slide.name + '"><figcaption>' + slide.name + '</figcaption>';
      heroCarousel.appendChild(figure);
    });

    if (slides.length <= 1) return;
    var activeIndex = 0;
    window.setInterval(function () {
      var slideEls = Array.prototype.slice.call(heroCarousel.querySelectorAll('.hero-slide'));
      if (!slideEls.length) return;
      slideEls[activeIndex].classList.remove('is-active');
      activeIndex = (activeIndex + 1) % slideEls.length;
      slideEls[activeIndex].classList.add('is-active');
    }, 4200);
  }

  function renderProducts(products) {
    productGrid.textContent = '';
    comparisonBody.textContent = '';
    products.forEach(function (product) {
      productGrid.appendChild(createProductCard(product));
      comparisonBody.appendChild(createComparisonRow(product));
    });
    renderHero(products);
  }

  loadProducts()
    .then(function (data) {
      var products = Array.isArray(data.products) ? data.products : [];
      renderProducts(products);
      loadStatus.textContent = products.length + '件の商品を読み込みました。';
      window.setTimeout(function () {
        loadStatus.classList.add('is-hidden');
      }, 1600);
      console.info('[Outdoor Kitchen] loaded products:', products.length);
    })
    .catch(function (error) {
      loadStatus.textContent = '商品マスタを読み込めませんでした。ローカル確認時は簡易サーバーで開いてください。';
      console.error('[Outdoor Kitchen] product load failed', error);
    });
})();
