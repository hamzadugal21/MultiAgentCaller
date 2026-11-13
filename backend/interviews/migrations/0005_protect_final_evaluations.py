from django.db import migrations


FORWARD_SQL = """
CREATE OR REPLACE FUNCTION interviews_reject_final_evaluation_changes()
RETURNS trigger AS $$
BEGIN
    IF OLD.is_final THEN
        RAISE EXCEPTION 'Final candidate evaluations are immutable.';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS interviews_protect_final_evaluation
ON interviews_candidateevaluation;
CREATE TRIGGER interviews_protect_final_evaluation
BEFORE UPDATE OR DELETE ON interviews_candidateevaluation
FOR EACH ROW EXECUTE FUNCTION interviews_reject_final_evaluation_changes();

CREATE OR REPLACE FUNCTION interviews_reject_final_score_changes()
RETURNS trigger AS $$
DECLARE
    target_evaluation uuid;
BEGIN
    target_evaluation := COALESCE(NEW.evaluation_id, OLD.evaluation_id);
    IF EXISTS (
        SELECT 1
        FROM interviews_candidateevaluation
        WHERE id = target_evaluation AND is_final
    ) THEN
        RAISE EXCEPTION 'Scores for final candidate evaluations are immutable.';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS interviews_protect_final_score
ON interviews_criterionscore;
CREATE TRIGGER interviews_protect_final_score
BEFORE INSERT OR UPDATE OR DELETE ON interviews_criterionscore
FOR EACH ROW EXECUTE FUNCTION interviews_reject_final_score_changes();
"""


REVERSE_SQL = """
DROP TRIGGER IF EXISTS interviews_protect_final_score
ON interviews_criterionscore;
DROP FUNCTION IF EXISTS interviews_reject_final_score_changes();
DROP TRIGGER IF EXISTS interviews_protect_final_evaluation
ON interviews_candidateevaluation;
DROP FUNCTION IF EXISTS interviews_reject_final_evaluation_changes();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("interviews", "0004_candidateevaluation_overall_confidence_and_more"),
    ]

    operations = [
        migrations.RunSQL(FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
