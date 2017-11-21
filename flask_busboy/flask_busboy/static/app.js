$("#search-bar").submit(function(event) {
    event.preventDefault();
    search_query = $(this).children("input").val().trim();
    query_encoded = encodeURIComponent(search_query).replace(/%20/g, "+");
    window.location.href = "/search?q=" + query_encoded
})

$("#add-to-transfers").click(function(event){
    seasons = $("#season-checkbox input:checked")
        .map(function() {return this.value})
        .toArray()
        .join(',')

    if(title_type == 'series') {
        $(this).attr("href", "/add/" + title_id)
    } else {
        if(seasons == '') {
            alert('Please select some seasons');
        } else {
            $(this).attr("href", "/add/" + title_id + "?seasons=" + seasons)
        }
    }

})