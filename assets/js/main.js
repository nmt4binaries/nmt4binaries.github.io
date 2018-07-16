// Obfuscate email
$(function() {
    $("#fake_email").click( function(e) {
        var username = "gbalats",
        domain = "gmail.com";

        window.location.href = "mailto:" + username + "@" + domain;
    });
});


// Toggle sidebar
$(function() {
    $("#menu-toggle").click(function(e) {
        e.preventDefault();
        $("#theWrapper").toggleClass("toggled");
    });
});


// Open links in new tabs
$(function() {
    $(".icons")
        .find("a")
        .not("[id='fake_email']")
        .attr("target", "_blank");

    $("a[href^='http']")
        .not("[href*='gbalats.github.io']")
        .attr("target", "_blank");

    $("a.download-btn")
        .attr("target", "_blank");
});


// Initialize smooth scrolling
$(function() {
    smoothScroll.init({
        speed: 700
    });
});


// Google Map Modal
function renderMap(mapCenter) {
    // Basic map options
    var mapOptions = {
        center: mapCenter,
        zoom: 14,
        mapTypeId:google.maps.MapTypeId.ROADMAP
    };

    // Create map
    var map = new google.maps.Map(document.getElementById("mapCanvas"), mapOptions);

    // Create marker
    var marker = new google.maps.Marker({position: map.getCenter()});
    marker.setMap(map);

    // Zoom in when marker is clicked
    google.maps.event.addListener(marker, 'click', function() {
        map.setZoom(16);
        map.setCenter(marker.getPosition());
    });
}

$(function() {
    $('#uoaMapModal').on('shown.bs.modal', function(e) {
        var element = $(e.relatedTarget);
        var data = element.data("lat").split(',')
        renderMap(new google.maps.LatLng(data[0], data[1]));
    });
});


$(function() {
    $('#cclyzerModal').modal({
        show: false,
        backdrop : true,
        keyboard : true
    });
});

// Display icon text
$(function() {
    $('.icons > a').hover(
        function() {
            var target = $(this).data("target");
            $(".icons").parent().find(target).show();
        },
        function() {
            var target = $(this).data("target");
            $(".icons").parent().find(target).hide();
        }
    );
});
