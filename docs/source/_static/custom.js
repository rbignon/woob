$(document).ready(function() {
    $('ul.current a.reference span.pre').text(function (index, text) {
        text = text.replace(/woob\.(\w+)\.(.*)/, "$2");
        text = text.replace(/^(?!woob\.)(.*)\.([^\.]+)$/, "$2");
        return text;
    });
});
