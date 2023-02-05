    $('ul.current a.reference span.pre').text(function (index, text) {
        text = text.replace(/woob\.([\w\.]+)\.(.*)/, "$2");
        //text = text.replace(/^(?!woob\.)(.*)\.([^\.]+)$/, "$2");
        return text;
    });
    $('ul.current li').filter(function (index) {
        text = $(' > a > code > span', this).text();
        return text.match(/^(?!woob\.)(.*)\.([^\.]+)$/);
    }).remove();
