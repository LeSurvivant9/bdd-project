-- Exemple: nombre de groupes
SELECT COUNT(*) AS nb_groupes FROM groupe;
SELECT * FROM groupe;
SELECT * FROM groupe WHERE nom_groupe = “Collet Jeu”:

SELECT * FROM groupe WHERE nom_groupe LIKE 'Collet Jeu';

SELECT * FROM concert WHERE duree IS NULL;

SELECT * FROM groupe WHERE style = 'Rock' OR pays_origine = 'France';

SELECT * FROM groupe WHERE id_groupe IN (SELECT id_groupe FROM concert WHERE id_scene = 10);

SELECT nom_scene FROM scene s WHERE EXISTS (SELECT 1 FROM concert c WHERE c.id_scene = s.id_scene AND c.duree > '02:00:00');

SELECT nom_groupe FROM groupe g WHERE NOT EXISTS (SELECT 1 FROM concert c WHERE c.id_groupe = g.id_groupe);

SELECT g.nom_groupe FROM groupe g LEFT JOIN concert c ON g.id_groupe = c.id_groupe WHERE c.id_concert IS NULL;

SELECT g.style, AVG(s.montant) FROM sponsoring s JOIN concert c ON s.id_concert = c.id_concert JOIN groupe g ON c.id_groupe = g.id_groupe GROUP BY g.style;

SELECT g.style, AVG(s.montant) AS moyenne_sponsoring FROM sponsoring s JOIN concert c ON s.id_concert = c.id_concert JOIN groupe g ON c.id_groupe = g.id_groupe GROUP BY g.style;

SELECT b.nom, b.prenom, COUNT(a.id_concert) AS nb_concerts FROM benevole b JOIN affectation a ON b.id_benevole = a.id_benevole GROUP BY b.id_benevole, b.nom, b.prenom HAVING COUNT(a.id_concert) > 10;

SELECT c.id_concert, COUNT(DISTINCT a.role) AS roles_differents FROM concert c JOIN affectation a ON c.id_concert = a.id_concert GROUP BY c.id_concert;

SELECT nom_partenaire, montant, RANK() OVER (PARTITION BY id_partenaire ORDER BY montant DESC) AS classement FROM sponsoring;

SELECT c.date_concert, s.montant, SUM(s.montant) OVER (ORDER BY c.date_concert) AS cumul_sponsoring FROM concert c JOIN sponsoring s ON c.id_concert = s.id_concert;

SELECT * FROM concert WHERE duree BETWEEN '01:00:00' AND '02:00:00';

SELECT * FROM concert WHERE date_concert BETWEEN '2024-01-01' AND '2024-12-31';

